function fmtTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

export default function CohostPanel({ session, currentTopic, currentQuestion, questionEntries, onForceQuestion }) {
  function handleSpeak() {
    if (!currentQuestion || !window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(currentQuestion);
    window.speechSynthesis.speak(utterance);
  }

  return (
    <section className="panel" id="cohost-panel">
      <h2>AI Co-host</h2>

      <span className="eyebrow">Current topic</span>
      {currentTopic ? (
        <span className="topic-badge">{currentTopic}</span>
      ) : (
        <span className="status-line">Not detected yet</span>
      )}

      <div className="question-block">
        <div className="question-box">{currentQuestion || "No question generated yet."}</div>
        <div className="ai-disclaimer">🤖 AI assistant — not a student</div>
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
            <span className="tag">trigger: {q.reason}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
