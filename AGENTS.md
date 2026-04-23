# AGENTS.md — SeedEval

> Autonomous-agent instructions for building **SeedEval**, an evaluation harness for ByteDance Seedance video-generation models.
> Target: **AI Lab: Seed Agents Challenge** (Track 03 — AI DevTools for Video). Submission **April 27, 2026**. Demo **May 2, 2026**.
> Solo builder. Today is Thu Apr 23, 2026. Submission Mon Apr 27. **4 build days (Thu-Sun) + submit morning Mon.**
>
> **This file is the single source of truth.** If reality contradicts this file, update this file first, then write code.

---

## 0. Prime Directives (read these first, obey them always)

1. **Ship > perfect.** Every decision optimizes for a working demo on April 27, not a clean codebase. Technical debt is acceptable; a broken submission is not.
2. **The demo is the product.** Until demo day, every feature exists to serve the 2-minute demo video. If a feature doesn't show up on screen in those 2 minutes, it's P1 or P2.
3. **Respect the judging weights: 40 / 40 / 20.** Video Output Quality (40%) + Agentic Execution (40%) + Demo & Presentation (20%). A DevTool in Track 03 that shows no video output *will lose*. Every eval we build must either display a Seedance video or visualize something computed *from* a Seedance video.
4. **Use the Seed family heavily and visibly.** Seedance for generation, Seed1.5-VL for visual judging, Seed1.6 for structured critique. Multi-model orchestration *is* the "Agentic Execution" score.
5. **Budget time, not features.** If a task runs over its time box by >50%, cut scope and move on. The day-by-day plan in §10 is a contract.
6. **No new dependencies after Day 3.** New deps introduce bugs. Freeze the stack early.
7. **The Python backend is the product. The React dashboard is the demo surface.** If forced to choose, backend completeness beats UI polish. But both must ship.

---

## 1. What We Are Building

### 1.1 One-sentence definition

SeedEval is an open-source evaluation harness that stress-tests ByteDance Seedance video-generation outputs across six dimensions — prompt adherence, temporal consistency, visual artifacts, cost/latency, safety, and version regression — and renders the results in an interactive React dashboard that makes failure modes visually obvious.

### 1.2 Why it deserves to exist

Every team shipping on Seedance faces the same problem: **video models are expensive, slow, and non-deterministic, so eval loops that work for LLMs (cheap, fast, cached) don't transfer.** Teams currently "eval" by eyeballing three outputs and shipping. SeedEval replaces that with a structured, multi-check, agentic pipeline that runs while the engineer sleeps and produces a diffable report in the morning.

### 1.3 The one-paragraph pitch (memorize this for the demo)

> "If you're building on Seedance, you know the pain: you tweak a prompt, wait 90 seconds, get a video, squint at it, and hope it's better. SeedEval turns that into a real eval loop. Point it at your Seedance pipeline, and a Seed1.6 orchestrator runs your prompts, uses Seed1.5-VL to grade every frame for prompt adherence, runs temporal consistency checks, flags artifacts, profiles cost, and produces a dashboard where every failure is one click from the frame that broke it. It's Langfuse plus a code-review suite, purpose-built for video agents."

### 1.4 What SeedEval is NOT

- **Not a video generator.** We don't train or fine-tune anything. We wrap Seedance, we don't replace it.
- **Not a benchmark leaderboard.** No VBench comparisons, no "here's our SOTA score." Pure developer tooling.
- **Not a SaaS.** No auth, no multi-tenant, no billing. Local-first open-source library + dashboard.
- **Not a general video QA tool.** Seed-family-first. Other models (Sora, Veo) are a post-hackathon concern.

---

## 2. Eval Suite: What Each Check Does (tiered by priority)

Six checks, tiered. **Build P0 first, in order. P1 only if on track at end of Day 3. P2 is demo-only — mock the output if needed.**

### 2.1 P0 — MUST SHIP (non-negotiable)

#### Check A: **Prompt Adherence** (VLM judge)
- **Input:** Seedance video + original prompt.
- **Algorithm:** Sample N=8 evenly-spaced frames from the video. Send each frame + prompt to Seed1.5-VL with a structured prompt asking: *"Rate 0–10 how well this frame matches the following prompt on (a) subject presence, (b) setting, (c) action, (d) style. Return JSON."* Aggregate per-frame scores with a trimmed mean (drop min + max to absorb first/last-frame weirdness).
- **Output:** Per-dimension score 0–10, per-frame score 0–10, overall score, and a one-sentence VLM-written "why it failed" string.
- **Why it lands on the demo:** This is the **hero check**. The demo will show a video that scored 7/10, then click through to the one frame where Seed1.5-VL said "the subject is missing in this frame," cutting to that exact frame. That is the "aha" moment.

#### Check B: **Temporal Consistency** (frame diffs)
- **Input:** Seedance video.
- **Algorithm:**
  1. Extract every frame with ffmpeg.
  2. Compute per-frame CLIP embeddings (use `openai/clip-vit-base-patch32` via HuggingFace — not a Seed model, but cheap and standard).
  3. Compute cosine similarity between consecutive frames → "smoothness curve."
  4. Compute cosine similarity between frame_i and frame_0 → "drift curve."
  5. Flag any frame where smoothness drops below `μ - 2σ` (statistical outlier — a visual jump) OR drift exceeds a threshold (subject identity loss).
- **Output:** Two line charts (smoothness, drift), flagged frame indices, thumbnails of flagged frames.
- **Why it lands on the demo:** The charts are visually compelling and instantly readable. "See this dip? That's where the character's face changed."

#### Check C: **Cost/Latency Profiling**
- **Input:** Every Seedance call made through our wrapper.
- **Algorithm:** Dead simple. Wrap each API call with a timer and a cost lookup table (per-model, per-second-of-video pricing pulled from provider docs). Log to SQLite.
- **Output:** Per-run cost in USD, wall-clock latency, API queue time vs. generation time if the provider splits them, and cumulative cost across a suite run.
- **Why it lands on the demo:** "This eval suite cost $2.40 and ran in 4 minutes." That's a quantified value prop judges can repeat.

### 2.2 P1 — SHIP IF ON TRACK at end of Day 3

#### Check D: **Visual Artifact Detection**
- **Input:** Seedance video.
- **Algorithm (hackathon version):** Use Seed1.5-VL with a *targeted* prompt per frame: *"Does this frame contain any of the following artifacts? (1) impossible anatomy (extra limbs, fused fingers), (2) text that is garbled or non-language, (3) physics violations (objects floating unnaturally), (4) temporal artifacts (ghosting, duplicated objects). For each, return boolean + 1-sentence evidence."*
- **Why P1:** The model does the work for us, but it's expensive (another VLM pass per frame) and the signal can be noisy. Ship only if Check A is rock solid.
- **Fallback if skipped:** Fold a single artifact question into Check A's prompt — "also flag any obvious visual artifacts" — and call it done.

#### Check E: **Regression Comparison (v1.5 vs 2.0)**
- **Input:** One prompt, run against two Seedance versions (e.g., Seedance 1.5 Pro and Seedance 2.0).
- **Algorithm:** Run Checks A + B + C on both. Compute delta on every metric. Flag regressions (any dimension where newer version scored lower).
- **Why P1:** The *implementation* is trivial (it's a loop over Check A–C), but it needs both model versions to be accessible through whatever API provider we end up with. Risk: credits might only cover one version.
- **Demo value if it works:** Huge. "Seedance 2.0 is better on prompt adherence but worse on temporal consistency for this prompt class." That is the kind of insight nobody currently has, and it sells the product instantly.

### 2.3 P2 — DEMO-ONLY IF TIME IS GONE

#### Check F: **Safety/NSFW Check**
- **Input:** Seedance video (sampled frames).
- **Algorithm:** Run frames through an open-source NSFW classifier (e.g., `Falconsai/nsfw_image_detection` on HuggingFace). Flag any frame above threshold.
- **Why P2:** Easy to implement (30 min with HF Transformers) but adds nothing to the hero demo narrative. Include it as a "we thought about safety" checkbox that appears in the dashboard.
- **Ship rule:** If it's Day 5 and this isn't done, ship a hardcoded "Safety: PASS" badge. Nobody is checking your classifier weights in a 2-minute demo.

---

## 3. System Architecture

### 3.1 High-level diagram (ASCII, because we'll be pasting this into Claude Code later)

```
┌─────────────────────────────────────────────────────────────────┐
│                         REACT DASHBOARD                          │
│  (Next.js 14 App Router, Tailwind, shadcn/ui, Recharts)         │
│  - Run list view  - Run detail view  - Frame inspector          │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST + SSE for live progress
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                             │
│  /runs           POST  start a new eval run                      │
│  /runs/{id}      GET   run detail + metrics                      │
│  /runs/{id}/stream  SSE per-step progress                        │
│  /runs/{id}/frames/{n}  GET  frame image + VLM critique          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR (Seed1.6)                         │
│  Plans the eval run: which checks, which order, which frames    │
│  Emits structured tool calls to each checker                     │
└─┬─────────────┬────────────┬────────────┬────────────┬──────────┘
  │             │            │            │            │
  ▼             ▼            ▼            ▼            ▼
┌─────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐
│ Gen │  │  Check A │  │  Check B │  │  Check C │  │ Others │
│ API │  │ Adherence│  │ Temporal │  │ Cost/Lat │  │ D/E/F  │
└─────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘
  │            │             │             │
  ▼            ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE (SQLite + FS)                       │
│  - runs.db           SQLite: runs, frames, scores, cost          │
│  - artifacts/        FS:     videos, frames, report JSONs        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Module layout (Python backend)

```
seedeval/
├── seedeval/
│   ├── __init__.py
│   ├── config.py              # env loading, API keys, feature flags
│   ├── models.py              # pydantic: Run, Frame, CheckResult, Score
│   ├── db.py                  # SQLite via sqlite3 stdlib — NO ORM
│   ├── storage.py             # FS helpers for videos/frames
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py            # abstract SeedanceProvider
│   │   ├── aimlapi.py         # concrete impl #1 (default if credits cover)
│   │   └── volcano.py         # concrete impl #2 (stub if no credits)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py    # Seed1.6-driven run planner
│   │   └── vlm_judge.py       # Seed1.5-VL wrapper for frame QA
│   │
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── base.py            # abstract Check class
│   │   ├── adherence.py       # Check A — P0
│   │   ├── temporal.py        # Check B — P0
│   │   ├── cost.py            # Check C — P0
│   │   ├── artifacts.py       # Check D — P1
│   │   ├── regression.py      # Check E — P1
│   │   └── safety.py          # Check F — P2
│   │
│   ├── pipeline.py            # ties orchestrator + checks + storage
│   │
│   └── api/
│       ├── __init__.py
│       ├── main.py            # FastAPI app
│       └── sse.py             # server-sent events for live progress
│
├── dashboard/                 # Next.js app (see §6)
├── tests/                     # pytest, P0 coverage only
├── pyproject.toml
├── README.md
├── AGENTS.md                  # this file
└── .env.example
```

### 3.3 Data model (SQLite schema, raw SQL)

Keep it dumb. No SQLAlchemy. Migrations are "drop the file."

```sql
CREATE TABLE runs (
  id              TEXT PRIMARY KEY,           -- ulid
  created_at      TEXT NOT NULL,
  prompt          TEXT NOT NULL,
  model           TEXT NOT NULL,              -- e.g. "seedance-2.0"
  video_path      TEXT,                       -- local fs path
  status          TEXT NOT NULL,              -- queued|generating|evaluating|done|failed
  total_cost_usd  REAL DEFAULT 0,
  total_latency_s REAL DEFAULT 0,
  overall_score   REAL,                       -- 0..10, weighted avg of checks
  raw_config      TEXT                        -- JSON blob of gen params
);

CREATE TABLE frames (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id      TEXT NOT NULL REFERENCES runs(id),
  idx         INTEGER NOT NULL,
  timestamp_s REAL NOT NULL,
  image_path  TEXT NOT NULL,
  embedding   BLOB                            -- CLIP embedding, float32 array
);

CREATE TABLE check_results (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id      TEXT NOT NULL REFERENCES runs(id),
  check_name  TEXT NOT NULL,                  -- "adherence" | "temporal" | ...
  score       REAL,                           -- 0..10 normalized
  passed      INTEGER,                        -- 0 | 1
  details     TEXT NOT NULL,                  -- JSON blob, check-specific
  created_at  TEXT NOT NULL
);

CREATE TABLE frame_critiques (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  frame_id    INTEGER NOT NULL REFERENCES frames(id),
  check_name  TEXT NOT NULL,
  score       REAL,
  flagged     INTEGER,
  reason      TEXT                            -- 1-sentence VLM output
);

CREATE INDEX idx_frames_run ON frames(run_id);
CREATE INDEX idx_check_run ON check_results(run_id);
CREATE INDEX idx_critique_frame ON frame_critiques(frame_id);
```

---

## 4. The Orchestrator Agent (the "Agentic Execution" 40%)

This is where we earn the Agentic Execution score. The orchestrator must *visibly* make decisions — not just be a for-loop with a Seed model name stapled on.

### 4.1 What the orchestrator does

Given a user's prompt and a generated video, the orchestrator:

1. **Classifies** the prompt into a category (portrait / landscape / action / abstract) using Seed1.6. Different prompt classes get different eval emphasis — a portrait prompt weights "subject consistency" heavily, an action prompt weights "temporal smoothness."
2. **Selects** which checks to run and with what parameters (e.g., "this prompt mentions 3 subjects → sample more frames for adherence").
3. **Schedules** checks, running cheap ones first (Check C — cost is free, Check B — just frame diffs) before expensive VLM calls (Checks A, D).
4. **Adapts** on the fly: if Check B finds a cluster of flagged frames at second 3.5, it tells Check A to sample extra frames in that window.
5. **Summarizes** at the end with a natural-language verdict: *"This generation passed temporal consistency but failed prompt adherence — specifically, the 'red dress' detail from the prompt is absent in 5/8 sampled frames."*

### 4.2 Implementation

```python
# seedeval/agents/orchestrator.py — sketch, not final

SYSTEM_PROMPT = """You are SeedEval, an agent that plans video evaluation runs.
Given a prompt and video metadata, you decide which evals to run and how.
You emit ONLY valid JSON matching the schema provided. No prose.
"""

def plan_run(prompt: str, video_meta: dict) -> RunPlan:
    """Single Seed1.6 call returning a structured plan."""
    response = seed16.chat(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_planning_query(prompt, video_meta)}],
        response_format={"type": "json_object"},
    )
    return RunPlan.model_validate_json(response)

def synthesize_verdict(results: list[CheckResult]) -> str:
    """Single Seed1.6 call turning structured results into a one-paragraph verdict."""
    ...
```

**Key design rule:** The orchestrator uses Seed1.6 *twice* per run — once to plan, once to summarize. **Not on every check.** Checks themselves are deterministic or use Seed1.5-VL. This keeps the architecture sane and costs down.

### 4.3 Why this scores on "Agentic Execution"

Judges have seen 100 "agents" that are just LLM → tool → LLM loops. Ours is different because:
- It **plans** (adaptive check selection based on prompt class)
- It **executes** (parallel check fan-out)
- It **reacts** (Check B feeds Check A's sampling strategy)
- It **synthesizes** (final natural-language verdict)

Explicitly call these four behaviors out in the demo: "plan, execute, react, synthesize." Those words go in the narration.

---

## 5. Technology Decisions (and the 30-second justification for each)

| Layer | Choice | Why |
|---|---|---|
| Seedance provider | **AIMLAPI** (`bytedance/seedance-1-0-lite-t2v` for Day 1–2, `seedance-1-0-pro-*` or `2-0-*` for demo fixtures) | Validated end-to-end Apr 23. Cheapest path, cleanest docs, async job pattern matches our design. Self-funded ($50 cap). |
| Backend language | Python 3.11 | Agent/ML ecosystem is Python-native. Zero friction. |
| Web framework | FastAPI | Async-first, built-in OpenAPI, pydantic v2 integration. |
| Validation | Pydantic v2 | Already the standard for structured LLM outputs. |
| DB | SQLite via stdlib `sqlite3` | No server, file-based, zero ops. Fits a hackathon perfectly. NO SQLAlchemy. |
| Task queue | None. Synchronous + SSE progress | Adding Celery/Redis is a day of yak-shaving. Run it inline, stream progress. |
| Video processing | `ffmpeg` via subprocess + `imageio-ffmpeg` for frame extraction | Stable, battle-tested, no Python video lib surprises. |
| Image embeddings | `open-clip-torch` (ViT-B/32) | CPU-fast, well-documented, standard for temporal diffs. |
| HTTP client | `httpx` | Async, works in FastAPI's loop. |
| Retries | `tenacity` | Video APIs fail. Exponential backoff with jitter. |
| Frontend | Next.js 14 App Router | Server components give clean data fetching; great for static export. |
| Styling | Tailwind + shadcn/ui | Unreasonably good defaults, zero time spent on design. |
| Charts | Recharts | Plays well with shadcn, enough for smoothness/drift curves. |
| Video player | Native `<video>` + custom frame scrubber | Anything more is scope creep. |
| Packaging | `uv` + `pyproject.toml` | Fast installs; the demo setup must be `uv sync && uv run seedeval ...`. |
| CI | GitHub Actions: ruff + pytest on PR | Signals professionalism without being time sink. |
| Deployment | None. Local-only. | Repo + README + demo video is the artifact. |

### 5.1 Decisions we are explicitly NOT making

- **No Docker.** Hackathon code runs on the builder's laptop. Dockerfiles can be a post-submission polish.
- **No auth.** Local tool.
- **No Postgres, no Redis, no Kafka, no Celery, no Temporal.** Every one of these is a trap.
- **No custom-trained models.** We orchestrate frontier APIs. That's the whole point.
- **No websockets.** SSE is enough for streaming progress and has half the failure modes.

---

## 6. Frontend (Dashboard)

### 6.1 Three pages, that's all

1. **`/`** — Run list. Table of recent eval runs. Columns: prompt (truncated), model, overall score, cost, status. Row click → run detail.
2. **`/runs/[id]`** — Run detail. Top: the generated video (autoplay muted loop). Below: per-check result cards with expand-to-drill-down. For Check A: clicking a flagged frame jumps the video to that timestamp. For Check B: Recharts line charts with flagged points highlighted.
3. **`/runs/[id]/frames/[idx]`** — Frame inspector (optional if time). Full-res frame + all VLM critiques about it.

### 6.2 Visual design principles

- **Dark mode only.** One less theme to design.
- **Monochrome + one accent.** Zinc base + orange (Seed brand-adjacent, not copied). Keep the eye on the data.
- **Every score is color-coded:** `0–4 red, 4–7 amber, 7–10 green`. Judges process this instantly.
- **Every data point is clickable.** A dashboard where you can't drill in is a PDF.
- **Loading states are live, not spinners.** SSE streams "Generating video... [45/90s]", "Extracting frames... [12/120]", "Judging frame 5/8...". Narrate the work.

### 6.3 The killer UI moment

On the run detail page, when a frame is flagged by Check A:
- The frame thumbnail appears with a red border.
- Click → video jumps to that timestamp + pauses.
- A tooltip shows Seed1.5-VL's verbatim critique.
- The prompt text at the top of the page highlights the specific words the VLM said were missing.

This is the 10-second clip that goes in the demo video. **Design the UI backward from this clip.**

---

## 7. The Seed Stack — Exact Model Roles

| Model | Role | Called where | Call frequency per run |
|---|---|---|---|
| Seedance 2.0 (or 1.5 Pro, whichever credits cover) | Generate the video being evaluated | `providers/*.py` | 1 (the run's input) |
| Seedance 1.5 Pro | Comparison version for Check E (regression) | `providers/*.py` | 1 (only if Check E enabled) |
| Seed1.5-VL | Frame-level visual judge for Checks A, D | `agents/vlm_judge.py` | N=8 (or 16 if adherence+artifacts both run) |
| Seed1.6 | Orchestrator: plan + synthesize | `agents/orchestrator.py` | 2 |

**Per-run Seed API call count: ~10–20.** Plan credit burn accordingly. Set a hard `MAX_RUNS_PER_DAY` env var to protect from runaway dev loops.

---

## 8. Algorithms (deep dive on the non-obvious bits)

### 8.1 Frame sampling strategy

Uniform sampling of N=8 frames is the default, but refine as follows:

- **Always include:** frame 0, last frame, middle frame. These three catch 80% of temporal errors.
- **Then fill:** 5 more, uniformly spaced between.
- **If Check B (temporal) has flagged clusters:** re-sample, adding 2 frames inside each flagged window (max 12 total).

**Why not every frame?** Seedance 2.0 outputs at 24fps × 5s = 120 frames. Judging every frame with Seed1.5-VL = 120 API calls per run. We'd be broke and slow. 8 frames catches nearly all prompt-adherence failures at 1/15 the cost.

### 8.2 VLM-as-judge prompt (Check A)

```
SYSTEM: You are a video-quality judge. You inspect single video frames and
rate how well each matches the user's original prompt. You return ONLY
valid JSON. No explanations outside the JSON.

USER: Original prompt: "{prompt}"

This is frame {idx} of {total}, taken at {timestamp}s.

Rate 0-10 on each dimension:
- subject_presence: Is the subject described in the prompt visible?
- setting_match:   Does the environment match what was described?
- action_match:    Is the action/motion consistent with the prompt?
- style_match:     Does the visual style match the prompt (e.g., "cinematic")?

Also return:
- overall: 0-10
- one_sentence_reason: plain-English, under 25 words
- flagged: true/false (true if any dimension <= 4)

Return JSON matching this exact schema:
{
  "subject_presence": int,
  "setting_match": int,
  "action_match": int,
  "style_match": int,
  "overall": int,
  "one_sentence_reason": str,
  "flagged": bool
}
```

**Why structured JSON and not free text:** we parse it into the DB, render it in the dashboard, and aggregate it. Free text is demo poison.

### 8.3 Temporal consistency math (Check B)

Given frames `f_0, f_1, ..., f_{n-1}` and their CLIP embeddings `e_i`:

```
smoothness[i]    = cos_sim(e_i, e_{i+1})     for i in [0, n-2]
drift[i]         = cos_sim(e_i, e_0)          for i in [0, n-1]

μ_s, σ_s         = mean, stdev of smoothness
flagged_smooth   = { i : smoothness[i] < μ_s − 2·σ_s }
flagged_drift    = { i : drift[i] < DRIFT_THRESHOLD }  # tune: 0.7 initial

temporal_score   = 10 · (|smoothness flags| + |drift flags|) / (2n)
                   then invert: 10 − temporal_score, clipped [0, 10]
```

Tuning note: the drift threshold is prompt-class-dependent. Abstract/landscape prompts drift naturally; portrait prompts should not. The orchestrator (§4.1) sets the threshold per run.

### 8.4 Overall score weighting

```
overall = 0.40 · adherence
        + 0.25 · temporal
        + 0.15 · artifacts    (if ran, else redistribute)
        + 0.10 · safety       (pass=10, fail=0)
        + 0.10 · (10 − normalized_cost)
```

Cost reward is there to visibly punish expensive generations. Weight tuning is allowed but must be a CLI flag, not a hardcoded change.

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ~~Seedance API access blocked / credits don't arrive in time~~ | ~~Medium~~ | ~~Fatal~~ | **MITIGATED — AIMLAPI + `seedance-1-0-lite-t2v` validated end-to-end Apr 23, 2026.** Smoke fixture saved at `fixtures/smoke_panda.mp4`. Budget: ~$35 expected, $50 cap. Still cache ALL video outputs locally — presigned URLs expire in 24 hours. |
| Seed1.5-VL latency too high for "live" demo | Medium | High | Pre-run 3 canonical eval runs the night before demo. Demo plays them from the DB. Live-run ONE new example at the end "because it's more convincing," but have a cached fallback. |
| Frontend eats too many days | High | Medium | Day 5 hard cap. If UI isn't ready by end of Day 5, ship a minimal HTML template rendered by FastAPI and record the demo against that. Ugly but functional beats polished but broken. |
| ffmpeg/CLIP issues on dev machine | Low | Medium | Day 1 smoke test: generate a test video, extract frames, compute embeddings. If this doesn't work on Day 1, nothing else matters. |
| Scope creep (you add a 7th check) | High | High | Re-read §0 Prime Directives. The answer is no. |
| Demo video production bombs | Medium | Fatal | Day 5 morning: first dry-run recording. Day 6: final cut. Do not leave recording to demo day. |
| You burn out | Medium | Fatal | One full night of real sleep Day 3 → Day 4. Sunk-cost on sleep loss is the #1 solo-hackathon killer. |

---

## 10. Day-by-Day Plan (the contract)

> Every day has a **"ship condition"** — an observable outcome. If the ship condition isn't met, cut scope on subsequent days, do not push the current day's work to tomorrow.

### Day 1 (Thu Apr 23) — Foundation
- Provider access: Seedance API working end-to-end (generate a 5s video, save to disk) — **smoke test already passed with `seedance-1-0-lite-t2v`, fixture saved**
- ffmpeg frame extraction working
- CLIP embeddings computed on extracted frames
- SQLite schema created, one row inserted and read back
- **Ship condition:** `uv run python -m seedeval.smoke_test` runs a real generation, extracts frames, computes embeddings, writes a DB row. End-to-end skeleton, no checks yet.

### Day 2 (Fri Apr 24) — Checks A, B, C (P0)
- Check A (adherence) fully working with Seed1.5-VL
- Check B (temporal) fully working with CLIP
- Check C (cost/latency) wrapping every provider call
- FastAPI `/runs POST` + `/runs/{id} GET` endpoints
- **Ship condition:** curl a POST, wait 2 minutes, GET back a JSON with 3 real scores.

### Day 3 (Sat Apr 25) — Orchestrator + Frontend skeleton
- Orchestrator agent (plan + synthesize) calling Seed1.6 (OR fallback to Claude/GPT if Seed1.6 unavailable via AIMLAPI — confirm on Day 2)
- Next.js app scaffolded, run list page reads from API
- SSE streaming progress wired end-to-end
- **Ship condition:** open the dashboard, see runs listed, click one, see video + 3 score cards.
- **Decision point at 6pm:** is Check D (artifacts) or Check E (regression) reachable in Day 4? If no, commit to shipping P0 only, polish instead.

### Day 4 (Sun Apr 26) — Polish + P1 (if reached) + frame inspector
- Frame inspector page: click flagged frame → video scrubs to that timestamp, VLM critique shown
- Recharts for Check B (smoothness + drift curves)
- Color-coded score system
- P1 checks (D and/or E) if decision was yes
- **Ship condition:** the "killer UI moment" (§6.3) works end-to-end on a cached run.

### Day 5 (Mon Apr 27 AM) — Demo video + SUBMIT
- **Morning (by 9 AM):** first full demo video take. Script finalized (§11). Screen recording done.
- **Late morning:** re-record if needed. README final pass. Push public. Submit.
- Submission deadline noon ET (verify exact time on submit form).
- **Ship condition:** SUBMITTED. Do not touch anything after submission.

### Day 6 (Tue Apr 28+) — Buffer / optional polish only
- If submission hit Day 5 cleanly, this is rest + decide about May 2 travel.
- If anything slipped, this is the last-chance day — but submission is already past.

---

## 11. The 2-Minute Demo Video (structure, scripted)

The judging guide says: ~1 min live demo, ~30s architecture, ~30s vision. Follow it exactly.

### 11.1 Minute 1 — Live demo (60s)

- **0:00–0:08** Hook. Black screen, text: *"Every team building on Seedance has the same problem."* Cut to: a Seedance-generated video playing. Voiceover: "You wait 90 seconds for this. And you have no idea if it's actually good."
- **0:08–0:20** Introduce the tool. Open the dashboard. Voiceover: "SeedEval runs your Seedance outputs through six checks, powered by the Seed family itself."
- **0:20–0:40** Show a run. Voiceover: "Here's a prompt. Here's the video it generated. Adherence: 6.2. Temporal consistency: 8.9. Cost: $0.34." Click the flagged frame. Video jumps to it. "Seed1.5-VL says: 'the red dress described in the prompt is not visible in this frame.' The dashboard highlighted those exact words up top."
- **0:40–1:00** Show the regression compare (if P1 shipped), else show the temporal curves. "You can now see failure modes you couldn't see before."

### 11.2 Minute 2 — Architecture + Vision (60s)

- **1:00–1:30** Architecture. Cut to §3.1 diagram on screen. Voiceover: "Under the hood: a Seed1.6 orchestrator plans the run, Seed1.5-VL judges every sampled frame, and a deterministic pipeline handles temporal and cost analysis. Multi-model agentic execution across the Seed family."
- **1:30–2:00** Vision. Voiceover: "SeedEval is open source. Post-hackathon it grows into a hosted CI integration — every PR that changes a prompt triggers a full eval suite. This is the tooling layer video-native teams need. Built on Seed, for Seed."

### 11.3 Production rules

- Screen recording at 1080p minimum. No 4K — too much to render.
- Voiceover recorded separately, not live. Tools: QuickTime for screen, any USB mic + Audacity for voice. Aim for *clear*, not *cinematic*.
- Do not show the code in the demo video. Judges are not reading code in 2 minutes.
- Do not apologize for anything in the voiceover. If a feature isn't done, it isn't in the video.

---

## 12. README.md contents (so the repo passes the judge's 10-second sniff test)

The README is the judge's second impression after the video. It must:

1. One-sentence pitch at the top, above the fold.
2. Animated GIF (or MP4 embed) of the dashboard under the pitch.
3. **Quickstart** — exactly 4 commands, copy-pasteable.
4. Links: demo video, AGENTS.md (this file), architecture diagram.
5. "Built with" badges: FastAPI, Next.js, Seed1.6, Seed1.5-VL, Seedance.
6. A "why this exists" paragraph — 3 sentences, no more.
7. License: MIT.

What the README must NOT have:
- Long feature lists
- Roadmap sections
- "About me" sections
- Anything that smells of GPT-generated padding

---

## 13. Submission Checklist (Day 6)

- [ ] GitHub repo is public
- [ ] README has pitch, GIF, quickstart, links
- [ ] Repo has MIT license
- [ ] Demo video is uploaded to YouTube (unlisted is fine) and linked from README
- [ ] `.env.example` exists, real `.env` is gitignored
- [ ] Submission form at betahacks.org/submit completed
- [ ] Luma event registration confirmed
- [ ] All hardcoded cache / fixture demo runs are checked into `fixtures/` so the repo demo works on a fresh clone without API credits
- [ ] Tag release `v0.1.0-hackathon` — a permanent pointer to the submission state

---

## 14. Rules for Coding Agents Working on This Repo

If a coding agent (Claude Code, Cursor, etc.) is working on this codebase:

1. **Read this file first. Every session. No exceptions.**
2. Do not introduce new top-level dependencies without updating §5.
3. Do not touch the SQLite schema in §3.3 without updating this file in the same commit.
4. If you hit a decision not covered here, stop and ask. Do not guess.
5. Do not add "clean architecture" layers. No DDD, no hexagonal. It's a hackathon; flat is faster.
6. Pydantic models live in `models.py`. One file. Don't scatter them.
7. Write tests ONLY for P0 checks and the orchestrator's JSON parsing. Nothing else.
8. Commit messages: imperative, <72 chars, reference the AGENTS.md section if relevant.
9. If a task takes >2 hours with no progress, stop and re-read §0 and §10.

---

## 15. Quick Reference: the numbers that matter

- **Submission:** Monday April 27, 2026, noon ET (self-imposed; site doesn't specify a time — verify on submit form Day 6 morning)
- **Demo day:** Saturday May 2, 2026, Computer History Museum, Mountain View CA
- **Scoring:** 40% Video Output Quality / 40% Agentic Execution / 20% Demo & Presentation
- **Demo length:** 2 minutes (1 min demo + 30s architecture + 30s vision)
- **P0 checks:** Adherence, Temporal, Cost
- **P1 checks:** Artifacts, Regression
- **P2 checks:** Safety
- **Seed models used:** Seedance 2.0, Seed1.5-VL, Seed1.6 (and Seedance 1.5 for Check E)
- **Lines of code target:** <3000 Python + <1500 TS. If you're above this, you're building too much.

---

*Last updated: Thu Apr 23, 2026 (provider locked to AIMLAPI, Seedance risk mitigated). If this date is more than 24 hours old, the plan is stale — check if reality still matches.*