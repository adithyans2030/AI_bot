// Session-lifecycle actions live here: the pre-session "Start" form, and
// (once a session is running) the "Wrap up unit" coverage action. This
// component decides which to render itself, based on whether `session` is
// set — App.jsx renders it unconditionally rather than swapping it out for
// the compact session-status-bar, since wrap-up needs to stay reachable
// for the whole time a session is active, not just before it starts.
export default function SessionPanel({
  session,
  statusText,
  onStart,
  canStart,
  onWrapUp,
  wrapUpResult,
  wrapUpPending,
  classMinutes,
  setClassMinutes,
}) {
  if (session) {
    return (
      <section className="panel" id="session-panel">
        <span className="eyebrow">Unit coverage</span>
        <div className="row">
          <button className="secondary" onClick={onWrapUp} disabled={wrapUpPending}>
            {wrapUpPending ? "Checking coverage…" : "Wrap up unit"}
          </button>
          {wrapUpResult && (
            <span className="status-line">
              {wrapUpResult.generated
                ? `Generated ${wrapUpResult.questions.length} wrap-up question(s) — ${Math.round(wrapUpResult.coverage_ratio * 100)}% of the unit now covered.`
                : wrapUpResult.message}
            </span>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="panel" id="session-panel">
      <h2>Start a session</h2>
      <p className="muted">
        Pick a unit, then start — the AI co-host begins listening once the session is running.
      </p>
      <label htmlFor="class-minutes">Class length (minutes)</label>
      <input
        id="class-minutes"
        type="number"
        min={10}
        max={300}
        value={classMinutes}
        onChange={(e) => setClassMinutes(e.target.value)}
      />
      <p className="muted">The AI co-host uses this to know when the class is near its end, for wrap-up.</p>
      <button onClick={onStart} disabled={!canStart}>
        Start session
      </button>
      <div className="status-line">{statusText}</div>
    </section>
  );
}
