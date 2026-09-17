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
                    (server-side rolling transcript buffer per session)
                                 │
              every ~5s, frontend polls POST /sessions/{id}/tick
                                 │
                    pacing gate (12s silence OR 4 min interval)
                                 │         not triggered → {triggered: false}
                                 ▼
        embed last ~90s of transcript → cosine similarity vs. stored
        unit chunks (local sentence-transformers + numpy, no paid API)
                                 │
                    top-3 chunks → Grok (xAI) question generation
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
- **LLM:** Grok via the OpenAI-compatible endpoint (`https://api.x.ai/v1`)
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
cp .env.example .env                  # then edit .env and set XAI_API_KEY
```

`XAI_MODEL`, all pacing thresholds, chunk sizes, and top-k are all in
`backend/app/config.py` (sourced from `.env`) — nothing is hardcoded
elsewhere. Verify the current model name and your account's free-credit
balance/rate limits in the [xAI console](https://console.x.ai) — don't
assume the placeholder in `.env.example` is still correct by the time you
read this.

**`.env` holds your real key and is git-ignored. `.env.example` must only
ever contain placeholders — never paste a real key into it.**

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
best there). The frontend and API share the same origin — no CORS.

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

Fast, offline unit tests (chunking, cosine similarity, pacing gate logic —
no model download, no network):

```bash
cd backend
pytest
```

### Manual end-to-end dry run (per the build order)

1. Start the server, open the app.
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

## Project layout

```
backend/
  app/
    config.py        # single source of truth: API key, model name, thresholds
    ingestion.py      # chunking (pure) + local embedding
    retrieval.py      # cosine similarity top-k search
    question_gen.py   # Grok API call, grounded prompt
    pacing.py         # silence/interval trigger gate (pure, testable)
    session_manager.py# in-memory runtime: transcript buffer + orchestration
    session_log.py     # event log + honest report generation
    storage.py         # local JSON persistence for units + sessions
    main.py             # FastAPI routes + static frontend mount
  data/                 # local JSON storage (git-ignored contents)
  tests/                 # pytest unit tests for ingestion/retrieval/pacing
frontend/
  src/
    App.jsx              # top-level state + layout
    api.js                # fetch wrapper for the backend
    components/            # UnitPanel, SessionPanel, TranscriptPanel,
                            # CohostPanel, NotesPanel, ReportPanel
    styles.css
  index.html / vite.config.js / package.json
  dist/                   # `npm run build` output — served by FastAPI (git-ignored)
samples/
  sample_unit_notes.txt / sample_transcript.txt   # for the manual dry run
```

## Out of scope for v1 (intentionally)

Joining Zoom/Meet/Teams as a real bot participant, speaker diarization, any
attendance tracking, multi-session dashboards/auth, mobile. These are
Phase 2 and are not stubbed anywhere in this codebase.
