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
      <h2>4. AI Co-host</h2>
      <div className="field">
        <strong>Current detected topic:</strong>
        <div>{currentTopic || "—"}</div>
      </div>
      <div className="field">
        <strong>Latest question:</strong>
        <div className="question-box">{currentQuestion || "—"}</div>
        <div className="row">
          <button onClick={handleSpeak} disabled={!currentQuestion}>
            🔊 Speak
          </button>
          <button className="secondary" onClick={onForceQuestion} disabled={!session}>
            Force question now (testing)
          </button>
        </div>
      </div>
      <label>Questions this session</label>
      <div className="scroll-box">
        {questionEntries.map((q, i) => (
          <div className="log-entry" key={i}>
            <span className="ts">{fmtTime(q.timestamp)}</span>
            {q.text} <em>(trigger: {q.reason})</em>
          </div>
        ))}
      </div>
    </section>
  );
}
