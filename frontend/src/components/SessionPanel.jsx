export default function SessionPanel({ session, statusText, onStart, onEnd, canStart }) {
  return (
    <section className="panel" id="session-panel">
      <h2>2. Session</h2>
      <div className="row">
        <button onClick={onStart} disabled={!!session || !canStart}>
          Start session
        </button>
        <button onClick={onEnd} disabled={!session}>
          End session
        </button>
      </div>
      <div className="status-line">{statusText}</div>
    </section>
  );
}
