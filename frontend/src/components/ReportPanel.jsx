export default function ReportPanel({ report }) {
  if (!report) return null;

  return (
    <section className="panel" id="report-panel">
      <h2>Session report</h2>
      <div className="report-body">
        <p className="ai-disclaimer">
          <strong>{report.ai_label}</strong> — one clearly-labeled AI assistant. No attendance
          figures are recorded or reported.
        </p>
        <div className="report-meta">
          <strong>Unit:</strong> {report.unit_name}
          <br />
          <strong>Start:</strong> {report.started_at_iso}
          <br />
          <strong>End:</strong> {report.ended_at_iso}
          <br />
          <strong>Duration:</strong> {report.duration_minutes} minutes
          <br />
          <strong>Unit coverage:</strong> {report.topics_covered} of {report.topics_total} unit topics touched
        </div>

        <h3>Topics matched ({report.topic_match_count} events)</h3>
        <ul>
          {report.topics_covered_preview.length ? (
            report.topics_covered_preview.map((t, i) => <li key={i}>{t}</li>)
          ) : (
            <li>(no topic matches recorded)</li>
          )}
        </ul>

        <h3>Questions asked by the AI co-host ({report.questions.length})</h3>
        <ul>
          {report.questions.length ? (
            report.questions.map((q, i) => (
              <li key={i}>
                [{q.timestamp_iso}] {q.question}{" "}
                <em>
                  ({q.trigger_reason}
                  {q.wrap_up ? ", wrap-up" : ""}
                  {q.audience === "class" ? ", to the class" : ""})
                </em>
                {q.agent_reason && <div className="status-line">Why the AI asked: {q.agent_reason}</div>}
              </li>
            ))
          ) : (
            <li>(no questions were generated this session)</li>
          )}
        </ul>

        {report.ai_decisions && report.ai_decisions.consulted > 0 && (
          <>
            <h3>AI controller decisions</h3>
            <ul>
              <li>
                Consulted {report.ai_decisions.consulted} times (
                {Object.entries(report.ai_decisions.by_action)
                  .map(([action, n]) => `${action}: ${n}`)
                  .join(", ")}
                )
              </li>
              <li>
                Fallbacks to the pacing rules: {report.ai_decisions.fallbacks}; vetoed by code checks:{" "}
                {report.ai_decisions.vetoed}; questions dropped as off-topic: {report.ai_decisions.rejected_off_topic}
              </li>
            </ul>
          </>
        )}

        <h3>Teacher notes ({report.teacher_notes.length})</h3>
        <ul>
          {report.teacher_notes.length ? (
            report.teacher_notes.map((n, i) => (
              <li key={i}>
                [{n.timestamp_iso}] {n.text}
              </li>
            ))
          ) : (
            <li>(none added)</li>
          )}
        </ul>
      </div>
    </section>
  );
}
