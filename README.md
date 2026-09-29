# Doubt-Clearing AI Co-host (v1 prototype)

An AI agent that sits in on college "doubt-clearing" sessions, listens to the
live transcript, figures out what topic is currently being discussed,
retrieves the relevant unit notes via RAG, and generates one plausible
student-style question at sensible intervals — so sessions that would
otherwise run silent produce something.

**Guardrail, always true:** this system is one clearly-labeled AI assistant.
It never impersonates a student, never fakes multiple participants, and never
records or reports attendance/presence data of any kind. Its end-of-session
report reflects only what the log actually captured.

v1 runs as a browser app fed by your mic (or pasted-in text for testing) —
not a bot that joins Zoom/Meet directly. See `BUILD_SPEC.md`-equivalent
context in the original brief for the Phase 2 plan.

## Architecture

```
Browser mic (Web Speech API) ──┐
Paste-in textbox ───────────────┼──► POST /sessions/{id}/transcript
                                 │
Screen share (optional) ──► frame every ~10s ──► POST /sessions/{id}/frame
                                 │                        │
                                 │          perceptual diff vs. last frame:
                                 │          unchanged → skip; changed → local
                                 │          vision model reads slide title/text
                                 │          (never triggers anything by itself)
                                 │
                    (server-side rolling transcript buffer per session)
                                 │
              every ~5s, frontend polls POST /sessions/{id}/tick
                                 │
                    pacing gate (12s silence OR 4 min interval)
                                 │         not triggered → {triggered: false}
                                 ▼
    embed last ~90s of transcript (+ slide title/text, if fresh) → cosine
    similarity vs. stored unit chunks, merged by max score per chunk
    (local sentence-transformers + numpy, no paid API)
                                 │
                    top-3 chunks → local LLM question generation (Ollama)
                                 │
              logged to session log (JSON) → shown in UI, optional TTS
                                 │
                  POST /sessions/{id}/end → report generated purely
                  from the log (no invented data, no attendance)
```

## Stack

- **Backend:** Python + FastAPI (`backend/app/`)
- **Embeddings:** `sentence-transformers` (`all-MiniLM-L6-v2`), fully local
- **Vector search:** in-memory numpy cosine similarity (no vector DB — the
  data volume per unit is a few thousand words, this is intentionally simple)
- **LLM:** a local model via [Ollama](https://ollama.com)'s OpenAI-compatible
  endpoint (`http://localhost:11434/v1`) — no API key, no credits, no
  account, no external rate limits, using the `openai` Python package
  rather than a provider-specific SDK. Model choice matters for latency:
  pick one that actually fits your GPU's VRAM (see Setup below)
- **Storage:** local JSON files under `backend/data/` — no database
- **Frontend:** React + Vite (`frontend/`). Production build (`npm run
  build`) outputs to `frontend/dist/`, which FastAPI serves directly at `/`
  — same-origin, no CORS to configure. Web Speech API for STT,
  `speechSynthesis` for optional TTS.

## Setup

```bash
cd backend
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Windows (git-bash):   source .venv/Scripts/activate
# macOS/Linux:          source .venv/bin/activate

pip install -r requirements-dev.txt   # includes pytest for the test suite
cp .env.example .env
```

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull gemma2:2b   # or a bigger model, if your GPU's VRAM can hold it
```

Make sure Ollama is running (the desktop app does this automatically;
otherwise `ollama serve`) before starting the backend. `LLM_MODEL`, all
pacing thresholds, chunk sizes, and top-k are all in `backend/app/config.py`
(sourced from `.env`) — nothing is hardcoded elsewhere.

**Model choice directly affects latency, not just quality.** If a model's
VRAM footprint exceeds your GPU's capacity, Ollama splits inference across
CPU and GPU, which is drastically slower — measured ~15x (163s vs 11s per
question) on a 4GB-VRAM GTX 1650 going from a 5.6GB-loaded model to a
2GB-loaded one. Check `ollama ps` after a request to see whether your model
landed on `100% GPU` or split — if it split, pick a smaller model.

### Optional: slide-aware topic matching

If the teacher shares a slide window (via the "Share slide" button, only
appears once a session is running), the app periodically reads it with a
second, vision-capable local model and uses the slide's title/text as an
*additional* topic-matching signal alongside the transcript — it never
replaces transcript matching, and it can never trigger a question by
itself; it only sharpens the existing pacing-gated tick. If sharing is
never used, nothing about this changes: pure transcript-only matching,
same as before this feature existed.

```bash
ollama pull moondream   # ~1.7GB, fits comfortably in 4GB VRAM
```

`LLM_VISION_MODEL` is separate from `LLM_MODEL` on purpose — the vision
call happens far more often (every ~10s of sharing vs. once per question),
so it needs to be small enough to stay fast; a 7B+ vision model would hit
the same slow CPU/GPU-split problem described above. A cheap perceptual
check (`SLIDE_FRAME_DIFF_THRESHOLD` in `.env`) skips the vision call
entirely when the slide hasn't visibly changed since the last frame.

> **Known limitation on this machine:** `ollama pull moondream` fails here
> with `tls: failed to verify certificate: x509: certificate signed by
> unknown authority` — a TLS-inspecting proxy/VPN on this network that
> Ollama's Go runtime doesn't trust, not a bug in this codebase. The
> merge/staleness/discard logic is fully implemented and covered by
> `tests/test_slide_session_integration.py` (mocks just the vision call),
> and the live endpoint was verified to fail gracefully — no crash, clean
> low-confidence fallback — when the model isn't present. The actual vision
> call itself needs testing on a network where the pull succeeds.

## Running

**Production-style (single origin, matches how it'll actually be used):**

```bash
cd frontend
npm install
npm run build          # outputs to frontend/dist/

cd ../backend
uvicorn app.main:app --port 8000
```

Then open `http://localhost:8000/` in Chrome (Web Speech API support is
best there) — that's the marketing/landing page. The actual tool is at
`http://localhost:8000/app`. Routing is client-side (`react-router-dom`);
the backend has a catch-all route that serves `index.html` for any
non-API, non-asset path, so `/app` also works on a direct hit, hard
refresh, or bookmark, not just when navigated to from `/`. The frontend
and API share the same origin — no CORS.

**Dev mode (hot reload while editing the React app):**

```bash
# terminal 1
cd backend
uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
npm install
npm run dev             # http://localhost:5173, proxies /units, /sessions,
                         # /health to :8000 (see vite.config.js)
```

Open `http://localhost:5173/` while developing; re-run `npm run build`
before relying on the backend to serve the app directly at `:8000`.

> Known, low-risk dev-only issue: `vite`'s bundled `esbuild` has an open
> advisory (GHSA-67mh-4wv8-2f99) that lets any page you visit in the same
> browser send requests to the Vite dev server while it's running. Doesn't
> affect the production build. Fixing it means a breaking Vite v8 upgrade —
> not worth it for a local prototype, but don't leave `npm run dev` running
> unattended on a shared machine.

## Testing

```bash
cd backend
pytest
```

Three kinds of coverage, in one run:
- **Pure-logic unit tests** (chunking, cosine similarity, pacing gate,
  frame-thumbnail diffing, vision-response parsing) — no model, no
  network, sub-second.
- **API integration tests** (`tests/test_api.py`, via FastAPI's
  `TestClient`) — real unit ingestion, real local embeddings, a full
  session lifecycle, and a regression test for the SPA-fallback routing.
  These never trigger question generation (no `force=True` tick on an idle
  session), so they don't need Ollama running — but they do load the
  embedding model for real, so the first run after a fresh interpreter is
  slow (~90s, one-time cold start), not instant.
- **Slide-signal integration tests** (`tests/test_slide_session_integration.py`)
  — the merge/staleness/discard logic around slide capture, with real
  embeddings but a mocked vision call (`slide_vision.read_slide`), so they
  don't need a vision model pulled. Includes a baseline-regression test
  confirming matching is untouched when slide capture is never used.

### Manual end-to-end dry run (per the build order)

1. Start the server, open `http://localhost:8000/app` (the tool, not the landing page).
2. Paste `samples/sample_unit_notes.txt` into the unit-material box, name it
   "Binary Search Trees", save it.
3. Start a session against that unit.
4. Use paste-in mode to feed in chunks of `samples/sample_transcript.txt`
   (paste a paragraph at a time, a few seconds apart, to simulate a live
   lecture) — or click "Force question now (testing)" to bypass the pacing
   gate and check question quality immediately.
5. Confirm the retrieved topic and generated question are actually about
   BST deletion / search, not something unrelated.
6. End the session and check the report: duration, topics matched, every
   question with a timestamp, any teacher notes — and confirm there is no
   attendance figure anywhere in it.
7. Optional: pull a vision model (`ollama pull moondream`) and click
   "Share slide" during a session, sharing a window with the unit's slides.
   Watch the status line for a detected slide title; end the session and
   confirm at least one question in the report has `slide_informed: true`.
   Stop sharing mid-session (either button) and confirm nothing breaks —
   matching should just fall back to transcript-only after ~30s.

## Project layout

```
backend/
  app/
    config.py        # single source of truth: local-LLM URL/model, thresholds
    ingestion.py      # chunking (pure) + local embedding
    retrieval.py      # cosine similarity top-k search
    question_gen.py   # local LLM (Ollama) call, grounded prompt (+ optional slide text)
    slide_vision.py    # optional: reads a shared slide frame (separate local vision model)
    pacing.py            # silence/interval trigger gate (pure, testable)
    session_manager.py    # in-memory runtime: transcript buffer, slide state, orchestration
    session_log.py         # event log + honest report generation
    storage.py               # local JSON persistence for units + sessions
    main.py                   # FastAPI routes + static frontend mount + SPA fallback
  data/                         # local JSON storage (git-ignored contents)
  tests/                         # pytest: ingestion/retrieval/pacing/slide_vision (pure) +
                                  # test_api.py + test_slide_session_integration.py
frontend/
  src/
    main.jsx              # react-router-dom entry: "/" -> LandingPage, "/app" -> App
    App.jsx                # the tool: top-level state + layout
    api.js                  # fetch wrapper for the backend
    config.js                 # frontend tunables (poll interval, frame-capture interval)
    components/                 # UnitPanel, SessionPanel, TranscriptPanel (mic +
                                 # optional slide capture), CohostPanel, NotesPanel, ReportPanel
    styles.css                    # tool theme, scoped under .app-shell
    pages/
      LandingPage.jsx              # marketing page (its own route, "/")
      LandingPage.css               # scoped under .landing-page
      ProductPreviewCard.jsx        # illustrative mock session card
  index.html / vite.config.js / package.json
  dist/                   # `npm run build` output — served by FastAPI (git-ignored)
samples/
  sample_unit_notes.txt / sample_transcript.txt   # for the manual dry run
```

## Out of scope for v1 (intentionally)

Joining Zoom/Meet/Teams as a real bot participant, speaker diarization, any
attendance tracking, multi-session dashboards/auth, mobile. These are
Phase 2 and are not stubbed anywhere in this codebase.
