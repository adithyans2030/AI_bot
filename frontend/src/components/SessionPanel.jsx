export default function SessionPanel({ statusText, onStart, canStart }) {
  return (
    <section className="panel" id="session-panel">
      <h2>Start a session</h2>
      <p className="muted">
        Pick a unit, then start — the AI co-host begins listening once the session is running.
      </p>
      <button onClick={onStart} disabled={!canStart}>
        Start session
      </button>
      <div className="status-line">{statusText}</div>
    </section>
  );
}
