# AI Co-host project: conversation log (25–26 Nov 2026)

A record of the conversation between the developer (**You**) and Claude Code
(**Claude**) about the Doubt-Clearing AI Co-host. User messages are quoted as
typed. Claude's replies are reproduced in full or near-full, and the work
Claude did on files is listed under **Actions**.

**Quick links**

- System documentation (Claude Doc): https://claude.ai/artifact/XKg4r55n6SMGMArnZEE4b1
- Code: this repository (`backend/`, `frontend/`)
- Where we stopped: [Current state and next steps](#current-state-and-next-steps) (end of this file)

---

## 1. Running the backend

**You:** how do i run the backend

**Claude:** You already have `backend/.venv` and `backend/.env` set up, so in
PowerShell it's:

```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Before you start it, make sure Ollama is running (the desktop app starts it,
or run `ollama serve`). You also need the model from your `.env`
(`gemma2:2b` by default): `ollama pull gemma2:2b`.

Opening the app:
- **With the built frontend:** run `npm install` and `npm run build` in
  `frontend/` once, then open `http://localhost:8000/app` in Chrome.
- **While editing the React code:** keep the backend running and run
  `npm run dev` in `frontend/` in a second terminal, then open
  `http://localhost:5173/`.

If something goes wrong:
- If PowerShell won't run `Activate.ps1`, run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` first.
- If `uvicorn` isn't found, run `pip install -r requirements-dev.txt` with the
  venv active.
- To check the server is up, open `http://localhost:8000/health`.

---

## 2. Full documentation of what was built

**You:** thank you now i want you to provide me the complete documentation of
what is built

**Actions:** Claude read the whole codebase, ran the test suite (60 passed),
and wrote a Claude Doc, **"Doubt-Clearing AI Co-host — System
Documentation"**: https://claude.ai/artifact/XKg4r55n6SMGMArnZEE4b1

Sections in that doc:
1. Overview: what it does, guardrails, out of scope
2. Architecture, with a diagram (4 inputs → pacing gate → topic match →
   question generation → session log → report)
3. Tech stack and repository layout
4. Backend modules (what each file in `backend/app/` does)
5. API reference (every endpoint)
6. Core logic: chunking, retrieval and coverage penalty, pacing gate, tick
   guardrails, question generation, wrap-up, slide vision, session log and
   report
7. Frontend (pages, components, API calls)
8. Configuration (every `.env` setting)
9. Setup and running
10. Testing (test files and what they check)
11. Moodle and Google Meet integration (added later, see section 7 below)
12. Known limitations and next steps

**Claude:** The documentation is ready, with an architecture diagram and the
latest test run (all 60 passed). Edit it inline or leave comments.

---

## 3. Taking it to production inside the university platform

**You:** ok good but now i want acutuall take this to production in the
realworld and also instead of deploying this as a seperate application i want
it to be integrated into the existing learning platform of the institution
this is the current demand "I have a product to create a agentic ai that sits
within a live class of a online session and as the teacher is teaching it
online ut asks certain question regarding the certain subject nothing outside
it and it's for Christ University online courses and its main motive is to
improve the morale of the teachers who teach soo that they don't get bored when
no one in the session is not asking or interacting with the teacher this agent
should be able to do that . What do you have on mind" and this message i have
got when i had a conversation with gemini and this is the response i have got
"" what do you think

**Claude (summary of reply):**

- The Gemini response didn't come through (the message ended with `""`).
- **The core carries over:** pacing, retrieval, grounding, coverage and the
  honest report. What changes is where it runs, where audio comes from and
  where data lives.
- **Integration route:** LTI 1.3, the standard way to plug a tool into Moodle,
  Canvas, Blackboard or D2L. The teacher clicks "AI Co-host" inside their
  course; sign-in and the "is this a teacher?" check come from the platform.
  Build: an LTI launch endpoint (teachers only), course-material import, and
  reports stored against the course.
- **The live-class tool matters more than the learning platform.** The
  prototype hears audio from the teacher's own browser tab, which works with
  any meeting tool. A bot that joins the call is different on each one (Zoom
  SDK, Teams calling bot, limited Meet bot access, BigBlueButton plugin).
- **Needed for real-world use:**
  1. Speech-to-text: Chrome's Web Speech API sends classroom audio to Google.
     Use self-hosted Whisper or an approved vendor, tested on Indian English.
  2. Model hosting: Ollama on each laptop won't scale, and `gemma2:2b` is too
     weak. Use a shared GPU server or an approved cloud LLM API.
  3. State and storage: JSON files → Postgres with pgvector; in-memory
     sessions → Redis.
  4. Privacy and consent: transcripts include students' voices. India's DPDP
     Act 2023 needs notice or consent, a retention period and access controls.
  5. Staying on topic: add a check that rejects questions not supported by the
     notes; let teachers rate or dismiss questions.
- **Hold firm:** never make the questions look like they come from students.
  Keep the "AI Co-host" label visible. Better still, have the AI direct some
  questions at the class ("can someone explain…?") to get real students
  talking.
- **Order:** confirm platform details with IT → harden the prototype → wrap as
  an LTI tool → pilot with 3–5 teachers → only then a meeting bot.

---

## 4. Gemini's response, and Claude's comparison

**You:** soo this was the response from gemmini

> **Gemini's response (pasted by you):**
>
> Building a real-time classroom agent requires an event-driven, low-latency
> streaming architecture rather than a standard request-response REST API.
> Because the agent must listen continuously, detect natural pauses, and never
> interrupt a live lecture, the system is split into an asynchronous Audio
> Ingestion & State Pipeline and a Decision & Guardrail Engine.
>
> **1. System Architecture Blueprint.** The pipeline operates in four
> continuous stages:
> - Meeting Ingestion Layer (The Bot): A headless virtual participant joins
>   the university's video conferencing platform (Zoom, Google Meet, or
>   Microsoft Teams) to capture raw WebRTC audio streams and post messages to
>   the meeting chat (or inject synthesized audio back into the room).
> - Real-Time Transcription & VAD Layer: Raw audio frames are streamed over
>   WebSockets to a Speech-to-Text (STT) engine with built-in Voice Activity
>   Detection (VAD) and speaker diarization (to distinguish the professor from
>   students). Transcripts are pushed into an in-memory rolling buffer.
> - The Orchestrator & Decision Loop: A lightweight background worker monitors
>   two signals: semantic boundaries (did the teacher just finish explaining a
>   concept or ask "Any doubts?"?) and silence duration (e.g., 6–10 seconds of
>   dead air). When triggered, it queries the course vector database and runs
>   an LLM evaluation.
> - Domain-Locked RAG & Delivery Layer: Before any question is emitted, it
>   passes through a strict topicality guardrail against the course syllabus.
>   If approved, it is sent via the meeting's chat API or streamed via
>   Text-to-Speech (TTS).
>
> **2. Recommended MVP Tech Stack**
>
> | Layer | Primary Recommendation | Alternative / Self-Hosted | Why |
> | --- | --- | --- | --- |
> | Meeting Bot Infrastructure | Recall.ai | Custom Puppeteer + WebRTC / Zoom Meeting SDK | Building headless bots for Zoom, Meet, and Teams from scratch takes months of maintenance. Recall.ai provides a single unified API to join calls, stream raw audio via WebSockets, and post chat messages. |
> | Voice & Agent Orchestration | LiveKit Agents (Python) | Pipecat (Daily) | Open-source, Python-native frameworks built for real-time audio/video AI loops, handling turn-taking, interruptions, and WebSocket buffering. |
> | Streaming Speech-to-Text | Deepgram (Nova-3) | AssemblyAI Universal-Streaming | Sub-300ms latency, strong accuracy on Indian-English academic accents, custom vocabulary boosting, native endpointing/silence detection. |
> | Orchestrator & Generation LLM | Gemini 2.5 Flash or GPT-4o-mini | Llama-3.3-70B (via Groq) | Ultra-low Time-To-First-Token (TTFT < 400ms) so the agent responds while the Q&A window is still open. |
> | Vector DB & Course RAG | Qdrant or pgvector | ChromaDB | Stores pre-chunked syllabus PDFs, lecture PPTs, and textbooks indexed by course_id and module_week. |
> | State & Rolling Buffer | Redis | In-memory Python deque | Holds the live 5-minute rolling transcript, cooldown timers (e.g., max 1 question every 12 minutes), and session state. |
> | Text-to-Speech (Phase 2) | Cartesia Sonic or ElevenLabs | Sarvam AI (Bulbul) | Sub-150ms latency with natural Indian-English voice profiles (Sarvam AI is particularly strong for authentic Indian academic cadence). |
> | Faculty Control Panel | Next.js / React + FastAPI | Streamlit | Web dashboard where a professor uploads their syllabus PDF, pastes the meeting link, and toggles Curiosity Level (Off / Chat Only / Voice + Chat). |
>
> **3. Core Engineering Logic (Preventing "Annoying Bot" Behavior)**
> - Rule 1: Hard Cooldown & Budget: a Redis TTL lock (e.g., 600 seconds)
>   after every intervention, capped at 3 to 5 interventions per 60-minute
>   lecture.
> - Rule 2: Human Priority Interrupts: if any real student unmutes or types in
>   the chat during the agent's 8-second silence countdown, abort the
>   generation and reset the timer. The agent only fills genuine voids.
> - Rule 3: Dual-Stage Prompting (Router → Generator): Step A (fast
>   classifier) on every 6-second silence returns JSON
>   `{"should_intervene": bool, "trigger_type": "teacher_prompted_qa | complex_concept_end | none"}`.
>   Step B (RAG generator) only if should_intervene: top-3 syllabus chunks,
>   one question (< 25 words), discard if cosine similarity < 0.72.
> - Rule 4: Pre-Class Ingestion Pipeline: PyMuPDF + LlamaIndex or LangChain to
>   parse slides and syllabus into metadata-tagged chunks (subject_code,
>   unit_number, allowed_topics).
>
> **4. Suggested 4-Week MVP Build Roadmap**
> - Week 1: syllabus RAG and logic (ingestion, pgvector/Qdrant, classifier and
>   guardrail loop tested on recorded lectures).
> - Week 2: meeting bot and live audio (Recall.ai + Deepgram, transcript
>   buffering and silence detection in a test Meet/Zoom room).
> - Week 3: chat-first MVP (post questions into meeting chat, dry runs with
>   2–3 faculty).
> - Week 4: faculty portal and voice option (dashboard for meeting links,
>   weekly slides, post-class summaries).

**Claude:** Build on the existing prototype and borrow about half of Gemini's
ideas. Its plan is a solid generic meeting-bot design, but it misses two key
requirements and has two risks.

**What Gemini misses**
1. **It's a separate application, which you said you don't want.** A
   "Faculty Control Panel" where teachers log in, upload a syllabus and paste
   a meeting link is the standalone product you're moving away from. LTI 1.3
   isn't mentioned. With LTI the course, teacher identity and often the
   meeting link come from the platform.
2. **It never says the AI must be identified.** "Authentic Indian academic
   cadence" voices plus diarization add up to an AI that sounds like a
   student. If discovered, the morale goal backfires. Keep the "AI Co-host"
   label in chat and voice.

**What to change**
- Recall.ai and Deepgram are third parties hearing every class, including
  students; needs IT and legal approval under the DPDP Act first.
- The 4-week roadmap is optimistic: starts from scratch and ignores app review
  and IT approval.
- LiveKit or Pipecat is overkill for chat-first delivery.
- The 0.72 similarity cutoff is a made-up number; scores depend on the
  embedding model, so it must be calibrated. The idea of a post-generation
  grounding check is right.
- The numbers contradict each other (600 s cooldown vs 1 question every 12
  minutes).

**What to adopt from Gemini**
1. **Human priority:** if a real student speaks or types, cancel the pending
   question. The best idea in the response.
2. **A per-lecture budget:** e.g. 3–5 questions per hour on top of the
   pacing gate.
3. **A teacher-prompted trigger:** "Any doubts?" followed by silence is the
   ideal moment.
4. **Chat-first delivery:** less intrusive than voice; voice opt-in.
5. **Structured ingestion:** PDFs and PPTs tagged by unit and week.
6. **A stronger hosted model:** `gemma2:2b` won't hold up.

**What changes earlier advice:** a meeting bot hears the whole room, while the
browser tab only hears the teacher's mic. So human priority and chat posting
really need a bot. Phasing: pilot with platform integration and browser-tab
capture (questions shown to the teacher, labelled); Phase 2 adds a meeting bot
once IT approves. You already have working pacing, grounding, coverage, the
honest report and 60 passing tests, so don't start over.

---

## 5. The university uses Moodle

**You:** the collge is using moodle as a platform and lms do this is mainly
used for thr online degree students

**Claude (summary):**
- **Use LTI 1.3, not a Moodle plugin.** The Moodle admin registers "AI
  Co-host" once as an External Tool; teachers add it like any activity. A PHP
  plugin would need installing and maintaining through every Moodle upgrade.
- **Teacher flow:** open the activity → Moodle signs them in automatically
  (identity, course, teacher role) → pick a course section → the tool pulls
  that section's files through Moodle web services → teach → report saved
  against the course.
- **Students** see nothing or a short notice that a labelled AI Co-host is
  used. Showing the notice protects the university.
- **Technical catch:** Moodle opens LTI tools in an iframe by default, which
  blocks microphone and screen sharing. Set the launch container to **New
  window**.
- **Code changes:** LTI endpoints (`/lti/login`, `/lti/launch`,
  `/.well-known/jwks.json`), auth on every route, Moodle content import
  (`core_course_get_contents`), HTTPS, Postgres, a hosted model.
- **Questions for the Moodle admin:** live-class tool? Moodle version? Will
  they register an LTI 1.3 tool and issue a web-services token? Where can the
  backend be hosted?

---

## 6. Their platform link

**You:** soo in had a go through on thier platform and this is the platform
link https://online.christuniversity.in/lms

**Actions:** Claude had a web-fetch agent read the public pages (no login).

**Claude:**

| Item | Finding | Evidence |
| --- | --- | --- |
| Platform | Moodle | LMS login at `onlinecourses.christuniversity.in/login/index.php`; footer "Powered by Moodle" |
| Version | Probably Moodle 5.0 (April 2025) | Mobile-app link contains build `2025041400`. Inference: confirm with the admin |
| Theme | Moove (third-party theme) | Only changes the look |
| Login | Username and password only, no Google or Microsoft sign-on | Login page |
| Live-class tool | Unknown | Not on the public pages |

What this means: LTI 1.3 is the right route (Moodle 5.0 fully supports it,
including dynamic registration). With no single sign-on, the LTI launch is how
the tool knows who the teacher is. Students on the Moodle mobile app aren't
affected; the co-host is for teachers on a laptop.

---

## 7. Live classes use Google Meet

**You:** the live classes are taken through google meet

**Claude:**

**What Google Meet allows**
- No official way for an outside bot to join and listen. Recall.ai-type
  services join as a browser guest; university-only meetings may refuse or
  require admission, and the Google admin must allow it. Meet Media API was
  still a developer preview when last checked.
- Meet's own transcripts arrive only after the meeting (in Google Drive).
- No public API lets an app post into Meet's chat.

**Approach for the pilot:** the teacher shares their Meet tab with the
co-host, with "Also share tab audio" ticked. That gives:
1. **Students' voices** from the tab audio. Meet doesn't play your own voice
   back, so this channel carries only other participants.
2. **The teacher's voice** from the microphone. One channel per side, so no
   speaker recognition needed.
3. **The teacher's slides**, because whatever they present appears in the tab.

This gives Gemini's **human priority** cheaply: when the tab audio shows a
student speaking, cancel the pending question and reset the silence timer. It
only needs voice-activity detection in the browser; students' speech is never
transcribed or sent anywhere.

**Delivery:** in the pilot, questions appear on the teacher's screen labelled
"AI Co-host asks". For students to see or hear the AI, Phase 2 needs a Meet
bot participant (Google admin approval).

| Phase | What | Needs from the university |
| --- | --- | --- |
| Pilot | Moodle LTI launch in a new window. Teacher mic plus Meet tab audio. Human priority. Labelled questions on the teacher's screen. Hosted model. | Moodle admin registers the LTI tool |
| Phase 2 | A Meet bot participant named "AI Co-host" that posts questions in chat | Google Workspace admin approval and a data-privacy review |

**Questions for IT:** Google Workspace for Education edition? Do students join
with university Google accounts? Where can the backend and model be hosted?

---

## 8. Building the pilot, and "is it agentic AI?"

**You:** yes go ahead and also what are we building here is it a agentic AI

**Actions (code written by Claude, not committed to git):**

New files:
- `backend/app/lti.py`: Moodle LTI 1.3 login and launch. Checks Moodle's
  signature, issuer, audience, deployment, nonce, expiry, message type and LTI
  version; one-time state plus a browser cookie. Teachers (Instructor or
  Administrator) get an 8-hour app token and land on `/app`; students get a
  notice page and no token. Also `/lti/jwks` (tool public key) and
  `/lti/setup` (values for the Moodle admin). Email is never requested.
- `backend/app/auth.py`: app tokens, `require_teacher`, course scoping for
  units, owner scoping for sessions. Sign-in is off locally
  (`AUTH_REQUIRED=false`).
- `frontend/src/vad.js`: browser voice-activity detection on the Meet tab's
  audio.
- Tests: `test_lti.py` (21), `test_auth.py` (7),
  `test_participant_priority.py` (7).

Changed files:
- `backend/app/config.py`: LTI and auth settings, `PARTICIPANT_HOLD_SECONDS`.
- `backend/app/pacing.py`: holds all triggers for 15 s after a class member
  speaks.
- `backend/app/session_manager.py`: session owner and course; participant
  activity (memory only, never logged or reported); a question is dropped if
  a student starts speaking while it's being generated (logged as
  `question_suppressed`); manual Force question is never dropped.
- `backend/app/main.py`: auth on every `/units` and `/sessions` route,
  `/auth/me`, `POST /sessions/{id}/activity`, LTI router.
- `backend/app/storage.py`: units carry their Moodle course id.
- `frontend/src/api.js`, `main.jsx`, `App.jsx`: token from the Moodle launch,
  sign-in gate, "Signed in as … · course".
- `frontend/src/components/TranscriptPanel.jsx`: **Share Meet tab** (slides +
  class audio), "questions on hold" indicator.
- `frontend/src/config.js`: `VAD_RMS_THRESHOLD = 0.02`,
  `VAD_MIN_SPEECH_MS = 300`, `ACTIVITY_POST_THROTTLE_MS = 2000`.
- `frontend/vite.config.js`: proxy for `/auth` and `/lti`.
- `backend/requirements.txt`: `PyJWT[crypto]==2.15.1`,
  `cryptography==50.0.2`, `python-multipart==0.0.34`.
- `backend/.env.example`, `.gitignore` (`backend/data/lti/` never
  committed), `README.md` (Moodle and Meet section).
- The Claude Doc gained a "Moodle and Google Meet integration" section with
  the production plan; test table and limitations updated.

**Results:** all **95** backend tests passed (60 before). Frontend built. A live
server with sign-in on behaved correctly (`/auth/me`, 401 without token,
`/lti/login` redirect to Moodle, `/lti/jwks`, `/app`).

**Claude's reply (summary):**
- Not yet verified: a real Moodle (tests use a simulated Moodle with its own
  signing key), a real Meet class (the `0.02` threshold needs tuning).
  Teachers need headphones, or the laptop mic picks up students from the
  speakers.

**Is this agentic AI?** Yes in the practical sense, deliberately not in the
buzzword sense.
- It's an agent: it runs on its own through the whole class, watches speech,
  slides and class audio, decides when to act and when to stay quiet, asks
  grounded questions and remembers what it covered. Nobody prompts it.
- It isn't "fully agentic": every decision (when to speak, student priority,
  whether there's enough to ground a question, what's on-topic) is ordinary
  testable code. The language model only writes the wording of each question.
- That's right for a live university class: predictable, explainable, can't
  wander off-topic, talk over a student or impersonate one. The accurate
  description is **a guardrailed AI agent**.

---

## 9. Making it completely agentic

**You:** i want to make it completely agentic no human intervention what
should i do

**Claude:** "Completely agentic" means two changes, and the second can't be
done in code alone.

**1. Remove the manual steps**

| Teacher does today | Hands-free replacement | Depends on |
| --- | --- | --- |
| Pastes unit notes | Agent imports course files from Moodle automatically | Moodle web-services token |
| Picks the unit | Agent works out the topic from the whole course's material, limited to that course | Only code |
| Clicks Start session | Scheduler reads class times and Meet links from Moodle or Google Calendar | Calendar access |
| Turns on mic, shares Meet tab | **A Meet bot joins** as a visible "AI Co-host" and hears everyone | **Google Workspace admin approval** |
| Reads the question on screen | Bot posts in Meet chat or speaks with text-to-speech | The bot |
| Clicks Wrap up unit | Agent runs wrap-up in the last ~10 minutes, or on "any final questions" | Only code |
| Clicks End session | Bot leaves when the meeting ends; report goes to the teacher in Moodle | Moodle messaging API |

The Meet bot is the hard dependency (Recall.ai or Google's Meet Media API;
both need the Google admin to allow it).

**2. Let the AI decide.** Turn the decision into an AI controller with a fixed
set of actions: `stay_silent`, `ask_question`, `ask_the_class`,
`run_wrap_up`, `leave`. Every few seconds it sees the recent transcript,
silence, slide, coverage, questions asked, time left and whether a student is
talking. **Code checks each action before it happens**: question budget,
student-priority hold, grounding check, AI label. Principle: "the AI proposes,
the rules decide". The current pacing gate becomes one of those checks.

**Keep, even at full autonomy:** teacher opt-in once per course; a way to stop
it (pause switch, or remove the bot from the call); the visible AI label and
no attendance tracking; audit logs. Hands-free also means every student's
voice goes to a server, which is a bigger DPDP review than the pilot.

**Suggested route:**
1. Build now (no approvals needed): the AI controller with fixed actions and
   code checks, automatic wrap-up, whole-course topic detection, Moodle
   content import tested against a local Moodle.
2. Ask the university for approvals: Google Workspace access for the bot,
   Moodle web-services and calendar access, privacy review.
3. Add the bot last and run hands-free with a few volunteer teachers first.

---

## 10. Saving this log

**You:** no as of now i want you to save all the conversation we had in this
chat as a conversational md file so that i can see it tommorow because my pro
is stopping on 26th

**Claude:** Saved as this file, `conversation-log.md`, in the project folder.

---

## Current state and next steps

**Where the code is**
- Pilot build done: Moodle LTI 1.3 sign-in, course and teacher scoping, Meet
  tab audio, human priority. 95 tests passing. **Not committed to git.**
- To commit it yourself:
  ```powershell
  git checkout -b moodle-meet-pilot
  git add -A
  git commit -m "Add Moodle LTI 1.3 sign-in and Meet tab human priority"
  ```
  Check `git status` first so nothing secret (like `backend/.env`) is added;
  `.gitignore` already excludes `.env` and `backend/data/lti/`.

**How to run**
- Local (no sign-in): as in section 1. Sign-in stays off while
  `AUTH_REQUIRED=false` in `backend/.env`.
- Tests: `cd backend`, activate the venv, `pytest`.
- Real Moodle: host on HTTPS, set `TOOL_BASE_URL`, open `/lti/setup` for the
  admin's values, then fill `LTI_PLATFORM_ISSUER`, `LTI_CLIENT_ID`,
  `LTI_DEPLOYMENT_IDS` and set `AUTH_REQUIRED=true`.

**Not yet verified**
- Launch from a real Moodle (only a simulated Moodle so far).
- Speech-detection threshold in a real Meet class.

**Open questions for the university**
1. Google Workspace for Education edition for Meet?
2. Do students join Meet with university Google accounts?
3. Can the backend and model run on university servers, or an approved cloud?
4. Can the Moodle admin confirm the version (5.0?) and register an LTI 1.3
   tool, plus issue a web-services token?

**Next options (not started)**
- Set up a local Moodle 5.0 in Docker and test the real launch.
- Build the AI controller (fixed actions + code checks) for full agency.
- Pilot hardening: hosted model, server-side speech-to-text, Postgres/Redis,
  Moodle content import, per-lecture question budget.

---

# Session 2 (26 Nov 2026): the AI controller

**You:** hey → Claude found the pilot already committed by you (`414774e`)
and listed three next steps.

**You:** build the AI controller

**What was built** ("the AI proposes, the rules decide"):

```
observe ──► precheck (code) ──► decide (LLM) ──► validate (code) ──► act
               │ hard "no"         │ fails            │ veto
               ▼                   ▼                  ▼
          stay silent      fall back to the     stay silent
          (LLM not called)  rules pacing gate
```

- New `backend/app/controller.py`: the AI picks one of `stay_silent`,
  `ask_question`, `ask_the_class`, `run_wrap_up` from a description of the
  moment (recent transcript, the teacher's last words, silence, slide,
  coverage, time left, wrap-up allowed yes/no).
- Code checks before the AI is asked: paused, student speaking, no content,
  90 s since the last question, 6 questions per hour, teacher still talking,
  consulted in the last 20 s.
- Code checks after: wrap-up only in the last 10 minutes and once; questions
  that score under 0.30 similarity to the course notes are dropped as
  off-topic; a student starting to speak still drops the question.
- If the model is down or replies with nonsense, the old pacing rules decide.
- `ask_the_class` uses a new prompt that invites students to answer, labelled
  as the AI.
- Teacher controls: class length at session start, a Pause co-host button,
  manual buttons still work.
- Audit: every decision logged; the report shows "why the AI asked" per
  question and a decision summary.
- `CONTROLLER_MODE=agent` (default) or `rules` (original behaviour).
- Tests: `tests/test_controller.py` (35) + `tests/conftest.py` keeps older
  tests on the rules path. All tests pass.

**Tested with the real local models (4 classroom moments):**
- `gemma2:2b`: ~1 s per decision, right about 11 of 12 times after the
  prompt was turned into an ordered checklist with a precomputed "wrap-up
  allowed" flag. Once it asked while the teacher was mid-sentence, even
  though its own reason said "teacher is mid-sentence".
- `llama3.1` (8B): 13-19 s per decision on the 4 GB GPU (78 s cold), and it
  also asked mid-sentence once. Too slow for live use on this machine.
- Conclusion: the controller works; a stronger hosted model is needed for
  real classes (`CONTROLLER_MODEL`).
- Off-topic check on the sample notes: on-topic questions scored 0.42-0.67,
  off-topic 0.10 or less, so 0.30 separates them (calibrate on real lectures).

**Not committed yet** (commit when ready).

**Next options:** a stronger hosted model for the controller; a local Moodle
in Docker to test a real launch; pilot hardening.

**Also fixed in session 2:**
- Saving session files could fail with "Access is denied" because the
  project sits in OneDrive, which briefly locks files while syncing.
  `storage.py` now retries the save briefly instead of crashing.
- `test_concurrent_ticks_fire_at_most_once` was flaky under load; its
  threads now start together.
- Final state: 130 backend tests, 4 full runs in a row all passing. A live
  end-to-end run (real server + gemma2:2b) waited while the teacher was
  talking, then asked a grounded question after "any doubts?", with the
  reason shown in the report.
