function fmtTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

const ACTION_LABELS = {
  stay_silent: "Staying silent",
  ask_question: "Asking a question",
  ask_the_class: "Asking the class",
  run_wrap_up: "Wrapping up",
};

const SOURCE_LABELS = {
  agent: "AI decision",
  guardrail: "rule check",
  fallback: "pacing rules (AI unavailable)",
};

export default function CohostPanel({
  session,
  currentTopic,
  currentQuestion,
  questionEntries,
  onForceQuestion,
  agentStatus,
  paused,
  onTogglePause,
}) {
  function handleSpeak() {
    if (!currentQuestion || !window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(currentQuestion);
    window.speechSynthesis.speak(utterance);
  }

  const lastEntry = questionEntries.length ? questionEntries[questionEntries.length - 1] : null;
  const toClass = lastEntry && lastEntry.text === currentQuestion && lastEntry.audience === "class";

  return (
    <section className="panel" id="cohost-panel">
      <h2>AI Co-host</h2>

      <span className="eyebrow">What the co-host is doing</span>
      <div className="row">
        <span className="status-line">
          {!session
            ? "Starts deciding on its own once a session is running."
            : agentStatus
              ? `${ACTION_LABELS[agentStatus.action] || agentStatus.action}: ${agentStatus.reason} (${SOURCE_LABELS[agentStatus.source] || agentStatus.source})`
              : "Listening and waiting for a good moment."}
        </span>
        <button className="secondary" onClick={onTogglePause} disabled={!session}>
          {paused ? "▶ Resume co-host" : "⏸ Pause co-host"}
        </button>
      </div>

      <span className="eyebrow">Current topic</span>
      {currentTopic ? (
        <span className="topic-badge">{currentTopic}</span>
      ) : (
        <span className="status-line">Not detected yet</span>
      )}

      <div className="question-block">
        <div className="question-box">{currentQuestion || "No question generated yet."}</div>
        <div className="ai-disclaimer">
          🤖 AI assistant — not a student{toClass ? " · addressed to the class" : ""}
        </div>
      </div>

      <div className="row">
        <button onClick={handleSpeak} disabled={!currentQuestion}>
          🔊 Speak
        </button>
        <button className="secondary" onClick={onForceQuestion} disabled={!session}>
          Force question now (testing)
        </button>
      </div>

      <span className="eyebrow">Questions this session</span>
      <div className="scroll-box">
        {questionEntries.length === 0 && <div className="empty-hint">No questions yet.</div>}
        {questionEntries.map((q, i) => (
          <div className="log-entry" key={i}>
            <span className="ts">{fmtTime(q.timestamp)}</span>
            {q.text}
            <span className="tag">
              {q.audience === "class" ? "to the class · " : ""}trigger: {q.reason}
            </span>
            {q.why && <div className="status-line">Why: {q.why}</div>}
          </div>
        ))}
      </div>
    </section>
  );
}
