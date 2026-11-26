import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { TICK_POLL_MS } from "./config.js";
import UnitPanel from "./components/UnitPanel.jsx";
import SessionPanel from "./components/SessionPanel.jsx";
import TranscriptPanel from "./components/TranscriptPanel.jsx";
import CohostPanel from "./components/CohostPanel.jsx";
import NotesPanel from "./components/NotesPanel.jsx";
import ReportPanel from "./components/ReportPanel.jsx";

function formatElapsed(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function App() {
  // {auth_required, authenticated, name, course_title} from /auth/me; null while loading.
  const [auth, setAuth] = useState(null);
  const [units, setUnits] = useState([]);
  const [selectedUnitId, setSelectedUnitId] = useState("");

  const [session, setSession] = useState(null); // {sessionId, unitId, unitName, startedAt, aiLabel}
  const [sessionStatus, setSessionStatus] = useState("No session running.");

  const [transcriptEntries, setTranscriptEntries] = useState([]);
  const [questionEntries, setQuestionEntries] = useState([]);
  const [notesEntries, setNotesEntries] = useState([]);
  const [currentTopic, setCurrentTopic] = useState("");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [report, setReport] = useState(null);

  const [wrapUpResult, setWrapUpResult] = useState(null);
  const [wrapUpPending, setWrapUpPending] = useState(false);

  // AI controller: planned class length, the teacher's pause switch, and
  // the latest decision ({action, reason, source}) shown for transparency.
  const [classMinutes, setClassMinutes] = useState(60);
  const [paused, setPaused] = useState(false);
  const [agentStatus, setAgentStatus] = useState(null);

  // Purely a display clock for the compact session bar's elapsed-time badge —
  // doesn't touch session/report state or the backend.
  const [nowTick, setNowTick] = useState(() => Date.now() / 1000);

  // A real local LLM call routinely takes longer than TICK_POLL_MS, so the
  // 5s poll can easily fire again before the previous tick() request has
  // even resolved. The backend now guards against this too (a per-session
  // lock), but skipping here avoids piling up redundant in-flight requests
  // at the source.
  const tickInFlightRef = useRef(false);

  async function reloadUnits() {
    setUnits(await api.listUnits());
  }

  useEffect(() => {
    (async () => {
      let me;
      try {
        me = await api.me();
      } catch (err) {
        me = { auth_required: false, authenticated: false };
        setSessionStatus(`Could not reach the server: ${err.message}`);
      }
      setAuth(me);
      if (me.auth_required && !me.authenticated) return;
      try {
        await reloadUnits();
      } catch (err) {
        setSessionStatus(`Could not load units: ${err.message}`);
      }
    })();
  }, []);

  useEffect(() => {
    document.title = "Doubt-Clearing AI Co-host";
  }, []);

  // Pacing-gate poll: only fires a question when the backend's pacing gate
  // (silence / max-interval trigger) actually allows it.
  useEffect(() => {
    if (!session) return undefined;
    const timer = setInterval(() => tick(false), TICK_POLL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  useEffect(() => {
    if (!session) return undefined;
    const timer = setInterval(() => setNowTick(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, [session]);

  async function startSession() {
    if (!selectedUnitId) {
      setSessionStatus("Save or select a unit first.");
      return;
    }
    try {
      const minutes = Number(classMinutes);
      const s = await api.startSession(selectedUnitId, minutes >= 10 && minutes <= 300 ? minutes : undefined);
      setSession({
        sessionId: s.session_id,
        unitId: selectedUnitId,
        unitName: s.unit_name,
        startedAt: s.started_at,
        aiLabel: s.ai_label,
      });
      setSessionStatus(`Session running — unit "${s.unit_name}". ${s.ai_label}.`);
      setTranscriptEntries([]);
      setQuestionEntries([]);
      setNotesEntries([]);
      setCurrentTopic("");
      setCurrentQuestion("");
      setReport(null);
      setWrapUpResult(null);
      setPaused(false);
      setAgentStatus(null);
    } catch (err) {
      setSessionStatus(`Error starting session: ${err.message}`);
    }
  }

  async function endSession() {
    if (!session) return;
    try {
      const finalReport = await api.endSession(session.sessionId);
      setReport(finalReport);
      setSessionStatus("Session ended.");
      setSession(null);
    } catch (err) {
      setSessionStatus(`Error ending session: ${err.message}`);
    }
  }

  async function sendTranscriptChunk(text) {
    if (!session || !text.trim()) return;
    const timestamp = Date.now() / 1000;
    setTranscriptEntries((prev) => [...prev, { timestamp, text }]);
    try {
      await api.postTranscript(session.sessionId, text, timestamp);
    } catch (err) {
      setTranscriptEntries((prev) => [
        ...prev,
        { timestamp, text: `[error sending to backend: ${err.message}]` },
      ]);
    }
  }

  async function tick(force) {
    if (!session || tickInFlightRef.current) return;
    tickInFlightRef.current = true;
    try {
      const result = await api.tick(session.sessionId, force);
      if (result.agent) setAgentStatus(result.agent);
      if (result.triggered) {
        setCurrentQuestion(result.question);
        if (result.topic_chunks && result.topic_chunks.length > 0) {
          setCurrentTopic(result.topic_chunks.map((c) => c.preview).join(" | "));
        }
        setQuestionEntries((prev) => [
          ...prev,
          {
            timestamp: result.timestamp,
            text: result.question,
            reason: result.reason,
            audience: result.audience,
            why: result.agent ? result.agent.reason : null,
          },
        ]);
      }
    } catch (err) {
      setSessionStatus(`Tick error: ${err.message}`);
    } finally {
      tickInFlightRef.current = false;
    }
  }

  async function togglePause() {
    if (!session) return;
    try {
      const res = await api.setPaused(session.sessionId, !paused);
      setPaused(res.paused);
      setAgentStatus(
        res.paused
          ? { action: "stay_silent", reason: "Paused by the teacher.", source: "guardrail" }
          : null
      );
    } catch (err) {
      setSessionStatus(`Pause error: ${err.message}`);
    }
  }

  async function addNote(text) {
    if (!session) return;
    try {
      const res = await api.addNote(session.sessionId, text);
      setNotesEntries((prev) => [...prev, { timestamp: res.timestamp, text }]);
    } catch (err) {
      setSessionStatus(`Note error: ${err.message}`);
    }
  }

  async function handleWrapUp() {
    if (!session) return;
    setWrapUpPending(true);
    try {
      const result = await api.wrapUp(session.sessionId);
      setWrapUpResult(result);
      if (result.generated) {
        // Reuse the exact same questionEntries shape/rendering tick()
        // already uses — "reason" already supports arbitrary trigger
        // labels, so a wrap-up question just becomes another one, tagged
        // accordingly, with no new UI needed in CohostPanel.
        setQuestionEntries((prev) => [
          ...prev,
          ...result.questions.map((q) => ({ timestamp: q.timestamp, text: q.question, reason: "wrap_up" })),
        ]);
        const last = result.questions[result.questions.length - 1];
        setCurrentQuestion(last.question);
      }
    } catch (err) {
      setSessionStatus(`Wrap-up error: ${err.message}`);
    } finally {
      setWrapUpPending(false);
    }
  }

  const pillMode = session ? "listening" : report ? "ended" : null;

  if (auth && auth.auth_required && !auth.authenticated) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <h1>Doubt-Clearing AI Co-host</h1>
        </header>
        <section className="panel">
          <h2>Open AI Co-host from Moodle</h2>
          <p className="muted">
            AI Co-host signs you in through your Moodle course. Go to your course, open the AI Co-host
            activity, and it will open here, signed in. If you just did that, your sign-in may have
            expired. Open it from Moodle again.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Doubt-Clearing AI Co-host</h1>
        <div
          className="ai-badge"
          title="This is a clearly labeled AI assistant. It is never disguised as a student and never used to fake attendance."
        >
          🤖 AI Co-host — assistant, not a student. One participant, always labeled.
        </div>
        {auth && auth.authenticated && (
          <div className="status-line">
            Signed in as {auth.name}
            {auth.course_title ? ` · ${auth.course_title}` : ""}
          </div>
        )}
      </header>

      {pillMode && (
        <div className="status-row">
          <span className={`status-pill ${pillMode === "listening" ? "listening" : ""}`}>
            {pillMode === "listening" ? (
              <>
                <span className="pulse-dot" />
                Listening…
              </>
            ) : (
              "Session ended"
            )}
          </span>
        </div>
      )}

      {session ? (
        <>
          <div className="session-status-bar">
            <div className="session-status-bar__meta">
              <span className="unit-name">{session.unitName}</span>
              <span className="timer">{formatElapsed(nowTick - session.startedAt)}</span>
            </div>
            <div className="session-status-bar__actions">
              <span className="status-line">{sessionStatus}</span>
              <button className="secondary" onClick={endSession}>
                End session
              </button>
            </div>
          </div>

          <SessionPanel
            session={session}
            onWrapUp={handleWrapUp}
            wrapUpResult={wrapUpResult}
            wrapUpPending={wrapUpPending}
          />
        </>
      ) : (
        <div className="setup-row">
          <UnitPanel
            units={units}
            selectedUnitId={selectedUnitId}
            setSelectedUnitId={setSelectedUnitId}
            reloadUnits={reloadUnits}
          />

          <SessionPanel
            statusText={sessionStatus}
            onStart={startSession}
            canStart={!!selectedUnitId}
            classMinutes={classMinutes}
            setClassMinutes={setClassMinutes}
          />
        </div>
      )}

      <main className="session-grid">
        <div className="col-transcript">
          <TranscriptPanel session={session} entries={transcriptEntries} onSendChunk={sendTranscriptChunk} />
        </div>

        <div className="col-side">
          <CohostPanel
            session={session}
            currentTopic={currentTopic}
            currentQuestion={currentQuestion}
            questionEntries={questionEntries}
            onForceQuestion={() => tick(true)}
            agentStatus={agentStatus}
            paused={paused}
            onTogglePause={togglePause}
          />

          <NotesPanel session={session} entries={notesEntries} onAddNote={addNote} />

          <ReportPanel report={report} />
        </div>
      </main>
    </div>
  );
}
