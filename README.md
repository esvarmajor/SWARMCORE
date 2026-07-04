# SWARMCORE

**A one-time-generated, replayable visualization of a multi-agent AI system's
reasoning trace — a human face rendered entirely in living code, on a dark
bio-mechanical / *System Shock* terminal.**

A dense green field of monospace characters out of which a **face made of code**
slowly resolves as three AI sub-agents do their work, alongside a live terminal
readout printing the swarm's actual reasoning. On the human-steering checkpoint
the whole face flushes amber. Built to be **screen-recorded** as a clean 15–25
second loop for a portfolio.

![status: EXECUTING / AWAITING INPUT / COMPLETE](https://img.shields.io/badge/status-EXECUTING%20%E2%86%92%20AWAITING%20INPUT%20%E2%86%92%20COMPLETE-39ff8a?labelColor=03060a)

---

## What this is (and what it isn't)

This is a **recorded artifact**, not a live interactive tool. It replays *one*
pre-generated agent run. There is no task-input box and nothing for a site
visitor to drive — you open it, it autoplays, it loops, you record it.

The agent trace it replays is **real Anthropic API output** — the orchestrator's
extended-thinking plan, each sub-agent's stated intent, the actual tool-use
blocks (real `web_search` + a custom `knowledge_lookup` tool), the tool results,
and each sub-agent's final output are all captured verbatim from live API calls.

**The one exception** is a single, deliberately-injected *human steering*
checkpoint. It is a fabricated moment showing a person editing a tool input
mid-flight (original vs. edited input + a one-line rationale). It is labeled
explicitly in the data with `"simulated_steering": true` and rendered on screen
as `SIMULATED — not a model action`, so it can never be mistaken for the model's
own behaviour. **Everything else in the trace is 100% real.**

---

## Repository layout

```
SWARMCORE/
├── trace-generator/
│   └── generate_trace.py     # makes real Anthropic API calls → trace.json
├── visualizer/
│   ├── index.html            # the self-contained replay (inline CSS + JS)
│   ├── trace.json            # the trace the visualizer replays
│   └── trace-data.js         # same trace as a JS fallback (for file:// use)
└── README.md
```

---

## Quick start (just watch it)

The visualizer is fully self-contained — no build step.

**Option A — open the file directly.** Double-click `visualizer/index.html`.
It loads the trace from `trace-data.js` (a browser blocks `fetch()` on
`file://`, which is why that JS fallback exists).

**Option B — static server (recommended for recording).**

```bash
cd visualizer
python3 -m http.server 8000
# then open http://localhost:8000
```

It autoplays on load and **loops** (with a ~2 s hold on the `COMPLETE` state)
so you never have to scrub.

### Playback controls

A minimal floating bar: **Play/Pause**, **Restart**, and a **1× / 2×** speed
toggle. Default is autoplay + loop.

---

## Regenerating the trace (make your own real run)

The committed trace was produced by `trace-generator/generate_trace.py`. To make
a fresh one you need Anthropic API credentials.

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...        # your key
python trace-generator/generate_trace.py   # writes visualizer/trace.json + trace-data.js
```

That's it — reload the visualizer and it replays the new run.

What the generator does (fixed, disciplined scope — one demo task, exactly three
sub-agents, one checkpoint):

1. **Orchestrator call** — Claude Opus 4.8 with extended (adaptive) thinking
   decomposes the fixed demo task *"Research and draft a 150-word brief on the
   current state of small modular nuclear reactors"* into exactly three subtasks
   (`research` / `analyze` / `write`) as structured JSON. The model's real
   thinking/plan text is captured verbatim.
2. **Three sub-agent calls with real tool use** —
   - `research` → real **`web_search`** server tool
   - `analyze` and `write` → a custom **`knowledge_lookup`** tool (a small
     client-side knowledge base) run in a real tool-use loop.
   For each we capture the stated intent, the real `tool_use` block, the tool
   result, and the final output.
3. **One injected steering checkpoint** — inserted into the `analyze` sub-agent
   after its first tool call is proposed but before it "executes": the original
   tool input, an edited version, and a rationale. Flagged `simulated_steering:
   true`. Nothing else is fabricated.

Each step carries a synthetic, evenly-spaced `timestamp_ms` (~1.1 s apart) so the
frontend can animate the replay at a natural pace.

> **Auth note.** The generator also accepts a Claude-Code-style OAuth bearer
> token via `ANTHROPIC_OAUTH_TOKEN` (it adds the required `oauth-2025-04-20` beta
> header for you). A standard `ANTHROPIC_API_KEY` is the simplest path.

### trace.json shape

```json
{
  "task": "…",
  "model": "claude-opus-4-8",
  "orchestrator": { "planning_text": "…", "subtasks": [ { "id", "role", "instruction" } ] },
  "subagents": [
    { "id", "role", "steps": [
      { "type": "reasoning" | "tool_call" | "tool_result" | "checkpoint",
        "content": …, "timestamp_ms": 0 }
    ] }
  ]
}
```

---

## The visualization

- **The face.** The centrepiece is a **typographic portrait** — a human face
  rendered entirely out of a dense field of monospace characters (a face *made of
  code*, drawn on an HTML canvas). The face is not pre-baked: it **materialises out
  of the noise** as the trace replays, brightening region by region as the three
  agents work, and holds fully-resolved on the `COMPLETE` state before the loop
  dissolves it back into code. Real words pulled from the trace (tool names,
  `SMR`, `ORCHESTRATOR`, …) are scattered faintly through the field.
- **Palette.** Near-black background (`#03060a`→`#060c08`) with a faint circuit
  texture and vignette; acid-green core `#39ff8a`, chrome-teal `#7fffd4`, amber
  checkpoint `#ffbe3d`, breach red `#ff3b3b`, chrome node borders `#dfe9e6`.
- **Replay.** As the trace plays in timestamp order, each step lights the active
  agent's zone of the face and fires an expanding **burst** of bright characters
  on every `tool_call` / `tool_result`. A slow scan-line and per-cell shimmer keep
  the whole field alive.
- **The checkpoint moment.** The **entire code-face flushes amber**, a **scanline
  sweep** crosses the canvas (`STATUS: AWAITING INPUT`), and the side terminal
  prints the original-vs-edited instruction and rationale with a typewriter
  effect. It holds ~2.5 s, then snaps back to green and resumes.
- **HUD.** A persistent header with the task name, an elapsed-time clock, and a
  `STATUS` readout that changes colour with state
  (`EXECUTING` → `AWAITING INPUT` → `COMPLETE`).
- **Terminal panel.** Fixed-width monospace, pale green/chrome text, a subtle
  scanline overlay, and a 1-frame chromatic-aberration glitch on state
  transitions.

The portrait is drawn on a **`<canvas>`** (procedural face-luminance mask →
per-character brightness), with SVG-free CSS effects for the sweep and glitch. No
frameworks, no external requests, no fonts fetched — it works fully offline.

---

## Recording a clip

1. Open the visualizer (static server recommended) and let it start looping.
2. Record the canvas with **QuickTime** ( *File → New Screen Recording* ), a
   browser extension, or OBS.
3. Crop to the canvas area. A single loop is ~15–25 s. Good export sizes:
   **1080×1080** (square, social) or **1920×1080** (landscape).
4. For a punchier clip, hit **2×**; for a calmer one, leave it at **1×**.

---

## Notes

- Built with vanilla HTML/CSS/JS — no dependencies at runtime.
- The generator targets `claude-opus-4-8` with adaptive extended thinking and
  real server/custom tools via the official `anthropic` Python SDK.
