#!/usr/bin/env python3
"""
SWARMCORE trace generator
=========================

Makes real Anthropic API calls to produce an authentic multi-agent reasoning
trace and writes it to ``trace.json`` for the visualizer to replay.

Structure produced:
  1. ORCHESTRATOR call  — extended thinking on, decomposes a fixed demo task
     into exactly 3 subtasks (research / analyze / write) as structured JSON.
     The model's real thinking/plan text is captured verbatim.
  2. THREE SUB-AGENT calls — each with real tool use:
        research : web_search
        analyze  : knowledge_lookup   (custom client-side tool)
        write    : knowledge_lookup   (custom client-side tool)
     For each we capture: stated intent, the real tool_use block, the tool
     result, and the model's final output for that subtask.
  3. ONE injected "steering" checkpoint — a fabricated-but-explicitly-labeled
     human edit inserted into subtask 2 (analyze). It carries
     ``"simulated_steering": true`` so it can never be mistaken for the model's
     own action. EVERYTHING ELSE IN THE TRACE IS REAL API OUTPUT.

Auth
----
  * Normal use:  export ANTHROPIC_API_KEY=sk-ant-...   then run this script.
  * OAuth use:   export ANTHROPIC_OAUTH_TOKEN=sk-ant-oat01-...   (a Claude Code
    style bearer token). The script sends the required
    ``anthropic-beta: oauth-2025-04-20`` header automatically.

Run
---
    python generate_trace.py                 # writes ../visualizer/trace.json
    python generate_trace.py out.json        # custom output path
"""

from __future__ import annotations

import json
import os
import sys

import anthropic

# ---------------------------------------------------------------------------
# Fixed demo configuration — deliberately small scope.
# ---------------------------------------------------------------------------
MODEL = "claude-opus-4-8"

# The demo task is the default, but can be overridden without editing the file:
#     export SWARMCORE_TASK="Summarize the 2025 state of solid-state batteries."
# The WHOLE pipeline adapts: the ORCHESTRATOR decomposes the task dynamically,
# RESEARCH uses live web_search, and the ANALYZE/WRITE ``knowledge_lookup`` KB
# (plus the simulated-steering target) is distilled from the research agent's
# real findings by ``build_knowledge_base`` — nothing task-specific is
# hardcoded anymore. The static SMR KB below survives only as a fallback.
_DEFAULT_TASK = (
    "Research and draft a 150-word brief on the current state of small modular "
    "nuclear reactors (SMRs)."
)
TASK = os.environ.get("SWARMCORE_TASK", _DEFAULT_TASK)

# Optional emotion-labeling pass (see label_emotions). On by default; set
# SWARMCORE_LABEL_EMOTIONS=0 to skip it (the visualizer then classifies with its
# built-in JS heuristic — the trace renders identically either way).
LABEL_EMOTIONS = os.environ.get("SWARMCORE_LABEL_EMOTIONS", "1") != "0"
# A cheap model is plenty for per-step labeling; override if desired.
EMOTION_MODEL = os.environ.get("SWARMCORE_EMOTION_MODEL", "claude-haiku-4-5-20251001")
# The six states MUST match the frontend STATE keys / the F·S·Y·D·A·R bus.
EMO_STATES = ["focus", "seek", "synthesis", "doubt", "alert", "resolve"]

# Synthetic timeline: evenly-spaced timestamps so the frontend can animate the
# replay at a natural pace. Real wall-clock latency is not used — the steps are
# spaced ~800-1500 ms apart.
STEP_GAP_MS = 1100


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
def build_client() -> anthropic.Anthropic:
    oauth = os.environ.get("ANTHROPIC_OAUTH_TOKEN")
    if oauth:
        # Claude Code style OAuth bearer token: Authorization: Bearer + beta hdr.
        return anthropic.Anthropic(
            auth_token=oauth,
            default_headers={"anthropic-beta": "oauth-2025-04-20"},
        )
    if os.environ.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    sys.exit(
        "No credentials. Set ANTHROPIC_API_KEY (recommended) or "
        "ANTHROPIC_OAUTH_TOKEN before running."
    )


client = build_client()


def text_of(content) -> str:
    """Concatenate all text blocks in a message's content list."""
    return "".join(b.text for b in content if b.type == "text").strip()


def thinking_of(content) -> str:
    return "".join(
        getattr(b, "thinking", "") for b in content if b.type == "thinking"
    ).strip()


# ---------------------------------------------------------------------------
# Custom "knowledge_lookup" tool — a small deterministic knowledge base the
# analyze/write sub-agents can query. Executed locally (client-side tool).
#
# The KB is built DYNAMICALLY from the research sub-agent's real findings (see
# build_knowledge_base), so the whole trace — not just research — adapts to any
# SWARMCORE_TASK. The static SMR KB below is only the fallback if that
# generation pass fails.
# ---------------------------------------------------------------------------
FALLBACK_KNOWLEDGE_BASE = {
    "smr_capacity": (
        "Small modular reactors are defined by the IAEA as reactors with an "
        "electrical output up to 300 MWe per module, roughly one-third of a "
        "conventional large reactor. Modules are factory-fabricated and shipped "
        "to site."
    ),
    "smr_deployment_status": (
        "As of 2024-2025 only a handful of SMRs operate commercially: Russia's "
        "floating Akademik Lomonosov (2x35 MWe) and China's HTR-PM (210 MWe). "
        "Most Western designs (NuScale, GE-Hitachi BWRX-300, Rolls-Royce SMR, "
        "X-energy) remain in licensing or early construction."
    ),
    "smr_economics": (
        "SMR economics hinge on factory serialization and learning-curve cost "
        "reductions. First-of-a-kind units are expensive; the NuScale/UAMPS "
        "project was cancelled in 2023 after target prices rose above ~$89/MWh. "
        "Order-book commitments (e.g. data-center power purchase agreements) are "
        "now driving renewed momentum."
    ),
    "smr_advantages": (
        "Claimed advantages: lower absolute capital cost per unit, passive "
        "safety systems, siting flexibility (including retiring coal plants), "
        "and load-following for grids with high renewable penetration."
    ),
}


FALLBACK_STEERING = {
    "key": "smr_economics",
    "rationale": (
        "prioritize economics/cost evidence over generic capacity facts for a "
        "decision-useful brief"
    ),
}


def run_knowledge_lookup(kb: dict, query_key: str) -> str:
    return kb.get(
        query_key,
        f"No knowledge-base entry for '{query_key}'. "
        f"Available keys: {', '.join(sorted(kb))}.",
    )


def make_knowledge_tool(kb: dict) -> dict:
    return {
        "name": "knowledge_lookup",
        "description": (
            "Look up a curated fact relevant to the current task from an "
            "internal knowledge base. Provide one of the available keys."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_key": {
                    "type": "string",
                    "enum": sorted(kb),
                    "description": "Which knowledge-base entry to retrieve.",
                }
            },
            "required": ["query_key"],
        },
    }


# ---------------------------------------------------------------------------
# Dynamic KB — distill the research sub-agent's real output into keyed facts.
# ---------------------------------------------------------------------------
def build_knowledge_base(research_summary: str) -> tuple[dict, dict]:
    """Distill the research sub-agent's findings into a keyed KB + a steering
    target, so analyze/write (and the simulated checkpoint) stay on-task for
    ANY SWARMCORE_TASK. Returns (kb, steering); falls back to the static SMR
    KB on any failure.
    """
    print("      -> distilling research findings into a task-specific KB...")
    schema = {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "short snake_case topic key",
                        },
                        "fact": {
                            "type": "string",
                            "description": "1-3 sentence factual summary",
                        },
                    },
                    "required": ["key", "fact"],
                    "additionalProperties": False,
                },
            },
            "steer_key": {
                "type": "string",
                "description": (
                    "the single entry a pragmatic human overseer would redirect "
                    "the analyst toward for a decision-useful deliverable"
                ),
            },
            "steer_rationale": {
                "type": "string",
                "description": "one short line, lowercase, no trailing period",
            },
        },
        "required": ["entries", "steer_key", "steer_rationale"],
        "additionalProperties": False,
    }
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Distill these research findings into an internal "
                        "knowledge base of 4-6 entries for downstream analyze/"
                        "write agents working on the task below. Each entry: a "
                        "short snake_case key and a dense, factual 1-3 sentence "
                        "summary grounded ONLY in the findings. Also choose "
                        "steer_key — the one entry a human overseer would "
                        "redirect the analyst toward to make the deliverable "
                        "decision-useful — plus a one-line steer_rationale.\n\n"
                        f"TASK: {TASK}\n\nRESEARCH FINDINGS:\n"
                        f"{research_summary[:5000]}"
                    ),
                }
            ],
        )
        data = json.loads(text_of(resp.content))
        kb = {
            e["key"]: e["fact"]
            for e in data["entries"]
            if e.get("key") and e.get("fact")
        }
        if len(kb) < 3:
            raise ValueError(f"only {len(kb)} usable KB entries")
        steer_key = data.get("steer_key")
        if steer_key not in kb:
            steer_key = sorted(kb)[1 % len(kb)]
        steering = {
            "key": steer_key,
            "rationale": data.get("steer_rationale")
            or FALLBACK_STEERING["rationale"],
        }
        print(f"      -> KB keys: {', '.join(sorted(kb))} · steer→{steer_key}")
        return kb, steering
    except Exception as ex:  # non-fatal: SMR fallback keeps the pipeline alive
        print(f"      !! dynamic KB failed ({ex}); using the static SMR fallback")
        return dict(FALLBACK_KNOWLEDGE_BASE), dict(FALLBACK_STEERING)


# ---------------------------------------------------------------------------
# Step 1 — ORCHESTRATOR
# ---------------------------------------------------------------------------
def run_orchestrator() -> dict:
    print("[1/4] orchestrator: decomposing task with extended thinking...")

    # --- Pass 1: real extended-thinking plan -------------------------------
    # Structured outputs suppress the summarized thinking stream, so we take the
    # plan in a plain call first and capture the model's real thinking verbatim.
    plan_resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": "high"},
        messages=[
            {
                "role": "user",
                "content": (
                    "You are the ORCHESTRATOR of a multi-agent system. Decompose "
                    "the task below into exactly THREE subtasks, one per role, in "
                    "this order: research, analyze, write. Think through how to "
                    "split it, then briefly describe your plan and the concrete "
                    "instruction you'd give each sub-agent.\n\n"
                    f"TASK: {TASK}"
                ),
            }
        ],
    )
    planning_text = thinking_of(plan_resp.content) or text_of(plan_resp.content)
    plan_text = text_of(plan_resp.content)

    # --- Pass 2: structured subtasks JSON, grounded in that plan -----------
    orchestrator_schema = {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": ["research", "analyze", "write"],
                        },
                        "instruction": {"type": "string"},
                    },
                    "required": ["id", "role", "instruction"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["subtasks"],
        "additionalProperties": False,
    }
    struct_resp = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        output_config={
            "format": {"type": "json_schema", "schema": orchestrator_schema}
        },
        messages=[
            {
                "role": "user",
                "content": (
                    "Convert this orchestration plan into exactly three subtasks "
                    "(ids t1, t2, t3; roles research, analyze, write in that "
                    "order), each with a concrete one-sentence instruction for the "
                    "sub-agent.\n\n"
                    f"TASK: {TASK}\n\nPLAN:\n{plan_text}"
                ),
            }
        ],
    )

    payload = json.loads(text_of(struct_resp.content))
    subtasks = payload["subtasks"]

    # Defensive: ensure exactly 3, correct roles/order.
    assert len(subtasks) == 3, f"expected 3 subtasks, got {len(subtasks)}"
    roles = [s["role"] for s in subtasks]
    assert roles == ["research", "analyze", "write"], roles

    print(f"      -> plan captured ({len(planning_text)} chars) · "
          f"{len(subtasks)} subtasks: {roles}")
    # plan_text (the model's visible plan) rides along so the visualizer can
    # give the orchestrator's thinking its own intro beat.
    return {
        "planning_text": planning_text,
        "plan_text": plan_text,
        "subtasks": subtasks,
    }


# ---------------------------------------------------------------------------
# Sub-agent helpers
# ---------------------------------------------------------------------------
def _first(content, block_type):
    for b in content:
        if b.type == block_type:
            return b
    return None


def run_research_subagent(subtask: dict) -> list[dict]:
    """Research sub-agent — real web_search server tool."""
    print("[2/4] research sub-agent: web_search...")
    steps: list[dict] = []

    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[
            {
                "role": "user",
                "content": (
                    "You are the RESEARCH sub-agent in a multi-agent system. "
                    "Before searching, briefly state your intent in one sentence. "
                    "Then use web_search to gather current facts.\n\n"
                    f"SUBTASK: {subtask['instruction']}"
                ),
            }
        ],
    )

    # Stated intent = leading text before the first server_tool_use.
    intent = ""
    for b in resp.content:
        if b.type == "text":
            intent += b.text
        elif b.type == "server_tool_use":
            break
    intent = intent.strip()
    if intent:
        steps.append({"type": "reasoning", "content": intent})

    # Extract the real search query + a compact view of the results.
    for b in resp.content:
        if b.type == "server_tool_use" and b.name == "web_search":
            steps.append(
                {
                    "type": "tool_call",
                    "content": {"name": "web_search", "input": dict(b.input)},
                }
            )
        elif b.type == "web_search_tool_result":
            results = []
            rc = b.content
            if isinstance(rc, list):
                for r in rc[:5]:
                    if getattr(r, "type", None) == "web_search_result":
                        results.append(
                            {
                                "title": getattr(r, "title", ""),
                                "url": getattr(r, "url", ""),
                            }
                        )
            steps.append(
                {
                    "type": "tool_result",
                    "content": {"name": "web_search", "results": results},
                }
            )

    # Final = the concluding synthesis AFTER the last search result — NOT the
    # leading intent (already its own step), so the intent isn't emitted twice.
    final_parts: list[str] = []
    seen_result = False
    for b in resp.content:
        if b.type == "web_search_tool_result":
            seen_result = True
            final_parts = []  # keep only the text following the LAST result
        elif b.type == "text" and seen_result:
            final_parts.append(b.text)
    final = "".join(final_parts).strip() or text_of(resp.content)
    steps.append({"type": "reasoning", "content": final, "final": True})
    return steps


def run_tool_subagent(
    subtask: dict,
    role: str,
    inject_checkpoint: bool,
    kb: dict,
    steering: dict,
) -> list[dict]:
    """analyze / write sub-agent — real custom knowledge_lookup tool loop over
    the task-specific KB.

    If ``inject_checkpoint`` is True, a fabricated-but-labeled human steering
    checkpoint is inserted AFTER the first tool call is proposed but BEFORE it
    'executes'. The rest of this function is 100% real API output.
    """
    label = "3/4" if role == "analyze" else "4/4"
    print(f"[{label}] {role} sub-agent: knowledge_lookup...")
    steps: list[dict] = []
    knowledge_tool = make_knowledge_tool(kb)

    system = (
        f"You are the {role.upper()} sub-agent in a multi-agent system. Before "
        "each tool call, state your intent in one short sentence. Use the "
        "knowledge_lookup tool to gather facts, then produce your final output."
    )
    if role == "write":
        system += (
            " Your final output must be the finished deliverable itself "
            "(the actual text the task asks for), not a description of it."
        )

    messages = [{"role": "user", "content": subtask["instruction"]}]
    checkpoint_done = not inject_checkpoint
    finalized = False

    for _ in range(8):  # bounded tool loop (KB has up to 6 keys + compose turn)
        # Force a tool call on the FIRST turn of the checkpoint agent, so the
        # simulated-steering checkpoint always has a real tool_use to attach to
        # (otherwise a model that answers directly would drop the ALERT moment).
        if not checkpoint_done:
            choice = {"type": "any", "disable_parallel_tool_use": True}
        else:
            choice = {"type": "auto", "disable_parallel_tool_use": True}
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2500,
            system=system,
            tools=[knowledge_tool],
            # one tool call per turn -> clean sequential steps for the replay
            tool_choice=choice,
            messages=messages,
        )

        intent = "".join(b.text for b in resp.content if b.type == "text").strip()
        tool_uses = [b for b in resp.content if b.type == "tool_use"]

        if resp.stop_reason != "tool_use" or not tool_uses:
            # Final answer — logged once, as final (not doubled as an intent).
            steps.append(
                {"type": "reasoning", "content": text_of(resp.content), "final": True}
            )
            finalized = True
            break

        if intent:
            steps.append({"type": "reasoning", "content": intent})

        # Handle every tool_use block (usually one, given disable_parallel).
        api_results = []
        for tu in tool_uses:
            original_input = dict(tu.input)
            effective_input = original_input

            # --- SIMULATED STEERING (fabricated, explicitly labeled) ----------
            if not checkpoint_done:
                edited_input = dict(original_input)
                # Redirect toward the KB entry a human overseer would flag —
                # chosen dynamically by the KB-distillation pass.
                edited_input["query_key"] = steering["key"]
                steps.append(
                    {
                        "type": "checkpoint",
                        "simulated_steering": True,
                        "content": {
                            "tool": "knowledge_lookup",
                            "original_input": original_input,
                            "edited_input": edited_input,
                            "rationale": "redirected: " + steering["rationale"],
                        },
                    }
                )
                effective_input = edited_input
                checkpoint_done = True

            steps.append(
                {
                    "type": "tool_call",
                    "content": {"name": "knowledge_lookup", "input": effective_input},
                }
            )
            result_text = run_knowledge_lookup(kb, effective_input.get("query_key", ""))
            steps.append(
                {
                    "type": "tool_result",
                    "content": {"name": "knowledge_lookup", "result": result_text},
                }
            )
            api_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result_text,
                }
            )

        # Continue the real conversation with the (effective) tool result(s) so
        # the model's subsequent output reflects the steered input.
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": api_results})

    if not finalized:
        # Loop budget exhausted while the model was still reaching for tools:
        # force a closing answer so the trace always ends with a deliverable.
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2500,
            system=system,
            tools=[knowledge_tool],
            tool_choice={"type": "none"},
            messages=messages,
        )
        steps.append(
            {"type": "reasoning", "content": text_of(resp.content), "final": True}
        )

    return steps


# ---------------------------------------------------------------------------
# Optional emotion-labeling pass.
# ---------------------------------------------------------------------------
# One cheap, batched Claude call per sub-agent labels each step with an
# emotional/cognitive state so the visualizer can drive colour + motion from a
# real model judgement instead of only its client-side heuristic. Fully
# back-compat: each label is written as an OPTIONAL nested ``step["emotion"]``
# field; if this pass is skipped or fails, the field is simply absent and the
# frontend falls back to its heuristic classifier (the trace still renders).
#
# Roadmap: this same enum-constrained pass is what lets an arbitrary,
# user-supplied task be labeled without touching the renderer — the hook for a
# hosted/parameterized "split the input less manually" model path.
EMOTION_RUBRIC = (
    "You label the EMOTIONAL / COGNITIVE state of each step of an AI sub-agent's "
    "reasoning trace, for a data-visualization. Choose exactly one state per step "
    "from this closed set:\n"
    "  focus     — calm reasoning / planning\n"
    "  seek      — reaching outward via a tool call / search\n"
    "  synthesis — integrating results, ranking, concluding (insight)\n"
    "  doubt     — noticing a mismatch, data-quality flag, contradiction, dead-end, "
    "uncertainty\n"
    "  alert     — a human steering checkpoint or a hard fault\n"
    "  resolve   — final, confident output / task complete\n"
    "For each step also give arousal 0-100 (mental energy), valence -1..1 "
    "(negative..positive), and conf 0..1 (your confidence in the label). Return one "
    "entry per step, aligned to the given [index] values."
)


def label_emotions(subagents: list[dict]) -> None:
    schema = {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "state": {"type": "string", "enum": EMO_STATES},
                        "arousal": {"type": "number"},
                        "valence": {"type": "number"},
                        "conf": {"type": "number"},
                    },
                    "required": ["index", "state", "arousal", "valence", "conf"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["labels"],
        "additionalProperties": False,
    }

    for agent in subagents:
        steps = agent["steps"]
        try:
            lines = []
            for i, s in enumerate(steps):
                c = s.get("content")
                txt = c if isinstance(c, str) else json.dumps(c)
                lines.append(
                    f"[{i}] type={s['type']} final={s.get('final', False)} "
                    f":: {str(txt)[:220]}"
                )
            resp = client.messages.create(
                model=EMOTION_MODEL,
                max_tokens=1500,
                system=EMOTION_RUBRIC,
                output_config={"format": {"type": "json_schema", "schema": schema}},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Sub-agent role: {agent['role']}. Label these "
                            f"{len(steps)} steps:\n" + "\n".join(lines)
                        ),
                    }
                ],
            )
            data = json.loads(text_of(resp.content))
            n = 0
            for item in data.get("labels", []):
                idx = item.get("index")
                if isinstance(idx, int) and 0 <= idx < len(steps):
                    steps[idx]["emotion"] = {
                        "state": item["state"],
                        "arousal": max(0, min(100, float(item.get("arousal", 50)))),
                        "valence": max(-1.0, min(1.0, float(item.get("valence", 0)))),
                        "conf": max(0.0, min(1.0, float(item.get("conf", 0.6)))),
                    }
                    n += 1
            print(f"      -> labeled {agent['role']}: {n}/{len(steps)} steps")
        except Exception as ex:  # non-fatal: leave this agent label-less
            print(f"      !! emotion labeling skipped for {agent['role']}: {ex}")


# ---------------------------------------------------------------------------
# Assemble the trace with a synthetic evenly-spaced timeline.
# ---------------------------------------------------------------------------
def stamp(subagents: list[dict]) -> None:
    t = 0
    for agent in subagents:
        for step in agent["steps"]:
            step["timestamp_ms"] = t
            t += STEP_GAP_MS


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "visualizer", "trace.json"
    )

    orchestrator = run_orchestrator()
    subtasks = orchestrator["subtasks"]

    subagents = []
    kb, steering = None, None
    for st in subtasks:
        if st["role"] == "research":
            steps = run_research_subagent(st)
            # distill the research agent's REAL findings into the KB that
            # analyze/write will query — the whole trace adapts to the task
            research_final = next(
                (
                    s["content"]
                    for s in reversed(steps)
                    if s["type"] == "reasoning" and s.get("final")
                ),
                "",
            )
            kb, steering = build_knowledge_base(research_final or TASK)
        else:
            if kb is None:  # research produced nothing usable
                kb, steering = (
                    dict(FALLBACK_KNOWLEDGE_BASE),
                    dict(FALLBACK_STEERING),
                )
            steps = run_tool_subagent(
                st,
                st["role"],
                inject_checkpoint=(st["role"] == "analyze"),
                kb=kb,
                steering=steering,
            )
        subagents.append({"id": st["id"], "role": st["role"], "steps": steps})

    if LABEL_EMOTIONS:
        print("[5/5] labeling emotional/cognitive states...")
        label_emotions(subagents)

    stamp(subagents)

    trace = {
        "task": TASK,
        "model": MODEL,
        "orchestrator": orchestrator,
        "subagents": subagents,
    }

    out_path = os.path.abspath(out_path)
    with open(out_path, "w") as f:
        json.dump(trace, f, indent=2)

    # Also emit a JS fallback so the visualizer works when index.html is opened
    # directly via file:// (where fetch('trace.json') is blocked by the browser).
    js_path = os.path.join(os.path.dirname(out_path), "trace-data.js")
    with open(js_path, "w") as f:
        f.write("window.SWARMCORE_TRACE = ")
        json.dump(trace, f, indent=2)
        f.write(";\n")

    print(f"\nWrote real trace -> {out_path}")
    print(f"Wrote file:// fallback -> {js_path}")
    n_steps = sum(len(a["steps"]) for a in subagents)
    print(f"  {len(subagents)} sub-agents, {n_steps} steps total")


if __name__ == "__main__":
    main()
