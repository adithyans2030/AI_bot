import { useEffect, useState } from "react";
import { api } from "./api.js";
import UnitPanel from "./components/UnitPanel.jsx";
import SessionPanel from "./components/SessionPanel.jsx";
import TranscriptPanel from "./components/TranscriptPanel.jsx";
import CohostPanel from "./components/CohostPanel.jsx";
import NotesPanel from "./components/NotesPanel.jsx";
import ReportPanel from "./components/ReportPanel.jsx";

const TICK_POLL_MS = 5000; // how often we ask the backend "is it time for a question?"

function formatElapsed(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function App() {
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

  // Purely a display clock for the compact session bar's elapsed-time badge —
  // doesn't touch session/report state or the backend.
  const [nowTick, setNowTick] = useState(() => Date.now() / 1000);

  async function reloadUnits() {
    setUnits(await api.listUnits());
  }

  useEffect(() => {
    reloadUnits();
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
      const s = await api.startSession(selectedUnitId);
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
    if (!session) return;
    try {
      const result = await api.tick(session.sessionId, force);
      if (result.triggered) {
        setCurrentQuestion(result.question);
        if (result.topic_chunks && result.topic_chunks.length > 0) {
          setCurrentTopic(result.topic_chunks.map((c) => c.preview).join(" | "));
        }
        setQuestionEntries((prev) => [
          ...prev,
          { timestamp: result.timestamp, text: result.question, reason: result.reason },
        ]);
      }
    } catch (err) {
      setSessionStatus(`Tick error: ${err.message}`);
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

  const pillMode = session ? "listening" : report ? "ended" : null;

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
      ) : (
        <div className="setup-row">
          <UnitPanel
            units={units}
            selectedUnitId={selectedUnitId}
            setSelectedUnitId={setSelectedUnitId}
            reloadUnits={reloadUnits}
          />

          <SessionPanel statusText={sessionStatus} onStart={startSession} canStart={!!selectedUnitId} />
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
          />

          <NotesPanel session={session} entries={notesEntries} onAddNote={addNote} />

          <ReportPanel report={report} />
        </div>
      </main>
    </div>
  );
}
