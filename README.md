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

<p align="center"><img src="docs/loop.gif" width="60%" alt="The face resolving out of the code as the agents run, flushing amber on the steering checkpoint"></p>

<p align="center"><em>▶ the loop, resolving out of the code — <a href="docs/loop.mp4">MP4 version</a></em></p>

![SWARMCORE — a face made of code beside a live agent-telemetry readout](docs/hero.png)

<p align="center"><img src="docs/face-green.png" width="49%" alt="The portrait resolved from the code field"> <img src="docs/face-amber.png" width="49%" alt="The face flushes amber on the human-steering checkpoint"></p>

---

## The idea

SWARMCORE is a piece of **generative data-art built on top of a real system**.
Underneath the aesthetic, an actual multi-agent pipeline ran: an **orchestrator**
model reasoned about a task and split it into three roles; three **sub-agents**
— *research*, *analyze*, *write* — went off and did the work, calling real tools
(live web search, a knowledge base) and passing results down the chain, with a
human reaching in **once** to steer a tool call mid-flight. Every reasoning step,
tool call, and result was captured to `trace.json`.

The visualization then replays that trace as a **portrait of the swarm's own
mind** — a human face rendered entirely from a churning field of monospace
characters. The face is not a picture pasted on top; it is *made of the run*.
As the three agents work, the portrait **resolves out of the noise**, and the
face **travels the colour wheel with its reasoning** — resting **blue** when it
thinks, **cyan** as it reaches for a tool, **green** as results land, **violet**
when it doubts its own data, **red** when a human reaches in to steer, and
**gold** as it resolves — one jewel-hue at a time. The mind **exhales its
actions**: on each tool call the action word (`WEB_SEARCH`, `KNOWLEDGE_LOOKUP`, …)
**fires outward** to the rim and waits there while the tool works, then on the
result the answer **rushes back in**, imprints into the word-face, and the whole
portrait **flares**. A compact **affect console** (mood word, arousal/valence, an
`F·S·Y·D·A·R` state bus, and a live EEG trace) lets you read the state as an
instrument. It's a single looping image that says, in one glance: *this is what a
collaborating group of AI agents — and the person guiding them — actually looks
like, and feels like, from the inside.*

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

**Optional environment overrides** (no code edits needed):

| Variable | Default | Effect |
|---|---|---|
| `SWARMCORE_TASK` | the SMR brief | Run the swarm on any task. The orchestrator + research (`web_search`) adapt to it; **note** the analyze/write `knowledge_lookup` KB and the steering are still SMR-specific (see Roadmap), so a non-SMR task gives a real research section but an SMR-flavored analyze/write section. |
| `SWARMCORE_LABEL_EMOTIONS` | `1` | Set `0` to skip the emotion-labeling pass (the frontend heuristic still colours the trace). |
| `SWARMCORE_EMOTION_MODEL` | `claude-haiku-4-5-20251001` | Which (cheap) model labels each step's emotional state. |

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
        "content": …, "timestamp_ms": 0,
        "emotion": {                       // OPTIONAL — added by the labeling pass
          "state": "focus" | "seek" | "synthesis" | "doubt" | "alert" | "resolve",
          "arousal": 0,                    // 0–100
          "valence": 0.0,                  // -1..1
          "conf": 0.0                      // 0..1 — used only when >= 0.5
        }
      }
    ] }
  ]
}
```

> The `emotion` field is **optional and additive**. If it's absent (as in the
> committed trace), the visualizer classifies each step with a built-in JS
> heuristic and renders identically — the label just lets a real model judgement
> override the heuristic when it's confident (`conf >= 0.5`).

---

## The visualization

- **The face.** The centrepiece is a **typographic portrait** — a human face
  rendered entirely out of a dense field of monospace characters (a face *made of
  code*, drawn on an HTML canvas). The face is not pre-baked: it **materialises out
  of the noise** as the trace replays, brightening region by region as the three
  agents work, and holds fully-resolved on the `COMPLETE` state before the loop
  dissolves it back into code.
- **A face made of real words.** The lit portrait is not random glyphs — the
  trace's actual vocabulary (`MODULAR NUCLEAR REACTORS`, `MEGAWATTS`, `NUSCALE`,
  `TERRAPOWER`, `ORCHESTRATOR`, `CONVECTION`, …) is **flowed through the bright mask
  cells in reading order**, so the face literally spells the run's own content. The
  dark background stays random and shimmers; the face's words are held stable (the
  churn skips them) and accrete as keywords fly in.
- **A face that expresses itself.** The mask is not static — six facial
  expressions are pre-built (one per state, on a **3× supersampled** canvas so the
  curves are smooth at glyph resolution) and the live face **eases between them**,
  so it *emotes* with real anatomy: angled brow ridges, **deep-set eyes** with lids
  that slide, pupils, and a specular catch-light, a curved mouth that smiles /
  frowns / gasps, nasolabial folds, a cheek lift, and a slight head tilt — plus a
  periodic **blink** and built-in asymmetry so it never reads as a dead mirror.
  Brows knit and eyes narrow on **DOUBT**; brows fly up, eyes widen and the jaw
  drops on **ALERT**; a Duchenne smile (mouth + cheeks + crinkled eyes) on **SYNTH**
  / **RSLV**. The skull is shared across expressions, so it emotes without wobbling.
- **Emotional / rational states — the full colour wheel.** Each replayed step is
  classified into one of six affective states, and the whole face **eases toward
  that state's colour and motion**. Because only *one* state is ever active, the
  face is a single jewel-hue at any instant that **travels the wheel over the run**
  — sequential colour, never a simultaneous rainbow. Harmony ("one material"): every
  core sits in a tight saturation/value band and every highlight blooms to *its own*
  tinted-white (a symmetric colour lerp), on a deliberately **hue-neutral graphite
  frame** so the travelling hue is the only chroma on screen.

  | State | Bus | Hue | Fires on | Expression + motion |
  |---|---|---|---|---|
  | **FOCUS** | `F` | blue `#3884ff` (home) | calm reasoning / planning | level gaze, resting breath |
  | **SEEK** | `S` | cyan `#2cd1f2` | a `tool_call` (reaching out) | brows arch, eyes widen + dart; L→R scan bar |
  | **SYNTH** | `Y` | green `#34e896` | results land / insight | Duchenne smile; bursts **collapse inward** + bloom |
  | **DOUBT** | `D` | violet `#9648f0` | mismatch / data-quality flag | knit brow, narrowed downcast eyes, **crimson furrow** + a **shudder** |
  | **ALERT** | `A` | red `#fa4023` | the human steering checkpoint | brows up, eyes wide, jaw drops; tremor + sweep |
  | **RSLV** | `R` | gold→white `#ffe373` | final, confident output | serene smile; **crystallizes** (churn drops, edges snap, holds) |

- **Action out, answer back.** The mind **exhales its action**: on a `tool_call`
  the tool/MCP word (`WEB_SEARCH`, `KNOWLEDGE_LOOKUP`, …) **fires outward** from the
  face to a rim anchor — with an expanding ring and a launch tracer — and hangs
  there, pulsing, while the tool "works out there." On the `tool_result` the answer
  **inhales back**: the word rushes home to a face cell with a *contracting* ring,
  **imprints into the word-face**, and the **whole portrait flares** to its own
  tinted-white (success). A dead-end result (no sources) instead **scatters** the
  word before it lands and the face flinches into doubt. Reasoning steps give a
  small outward *murmur* so idle thought still breathes. All flights are seeded, so
  the loop records identically.
- **Affect console.** A compact instrument (top-right): the current mood word,
  numeric **AROUSAL / VALENCE**, a six-segment `F·S·Y·D·A·R` **state bus** whose
  prior segments keep a decaying afterglow (so you read the *trajectory* of
  states), and a **live EEG trace** whose amplitude tracks arousal and whose shape
  changes per state (calm wave → jagged spikes on ALERT → flat line on RSLV).
- **Palette.** A **hue-neutral graphite frame** (near-black `#04060c`→`#070b12`
  background, cool-neutral circuit texture and vignette, graphite borders) so the
  JS owns every saturated pixel — the face's single travelling jewel-hue is the
  only chroma on screen. The six state hues are listed above.
- **Replay.** As the trace plays in timestamp order, each step lights the active
  agent's zone of the face. A slow scan-line and per-cell shimmer keep the field
  alive; the churn skips the face's word-cells so the vocabulary stays legible.
- **The checkpoint moment.** This is the **ALERT** state: the **entire face flushes
  red**, the eyes fly wide and the jaw drops, a **scanline sweep** crosses the canvas
  (`STATUS: AWAITING INPUT`), and the side terminal prints the original-vs-edited
  instruction and rationale with a typewriter effect. It holds ~2.5 s, then resumes.
- **The finale (signature).** On `COMPLETE`, the whole run's palette **sweeps across
  the face as a full-wheel rainbow** — the one instant every hue appears at once —
  then collapses into the serene **gold** resolve as the face settles into a smile
  and crystallizes, held for the loop's end-hold before it dissolves and repeats.
- **HUD.** A persistent header with the task name, an elapsed-time clock, and a
  `STATUS` readout that changes colour with the live state
  (`EXECUTING` → `AWAITING INPUT` → `COMPLETE`).
- **Terminal panel.** Fixed-width monospace, cool-neutral text, a subtle
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

## Roadmap — toward a live, less-manual pipeline

Today the trace is generated once (fixed scope) and replayed. The direction is to
make the whole thing **drive off arbitrary input with less hand-authoring**:

1. **Arbitrary tasks (partial).** `SWARMCORE_TASK` already lets the orchestrator
   decompose any task into sub-agents dynamically — the "split the input" step is
   the model's job, not a hardcoded list. The research agent (live `web_search`)
   adapts fully; the next step is making the analyze/write `knowledge_lookup` KB
   task-aware (or routing them through `web_search` for custom tasks) so the whole
   trace, not just research, is task-relevant.
2. **Model-labeled affect (shipped).** The emotion-labeling pass (`step.emotion`)
   is the seam where a model, not a hand-tuned heuristic, decides state. It is
   enum-constrained to the six frontend states, conf-gated, and back-compat.
3. **A hosted "router" model (next).** Replace the batched build-time call with a
   small hosted endpoint that, given raw input or a live step, returns
   `{state, arousal, valence, conf}` (and, for decomposition, the sub-agent split).
   The renderer already consumes exactly this shape, so nothing in the
   visualization changes — only *where* the labels come from. The Claude API is
   the reference implementation of that endpoint for now.
4. **Live streaming (later).** Point the visualizer at a live run instead of a
   recorded `trace.json`: stream steps in over WebSocket/SSE, classify each on
   arrival (client heuristic first, hosted model to confirm), and let the face
   react in real time — the same emotional instrument, but for a run happening now.

The design deliberately keeps the **renderer decoupled** from *how* states are
produced, so each step above is a drop-in swap behind the `step.emotion` contract.

---

## Notes

- Built with vanilla HTML/CSS/JS — no dependencies at runtime.
- The generator targets `claude-opus-4-8` with adaptive extended thinking and
  real server/custom tools via the official `anthropic` Python SDK; the optional
  emotion-labeling pass uses a cheaper model (`claude-haiku-4-5` by default).
- The six emotional states, the keyword-intake animation, and the affect console
  (mood / arousal-valence / `F·S·Y·D·A·R` bus / EEG) all run inside the single
  canvas render loop — no new dependencies, still fully offline.
