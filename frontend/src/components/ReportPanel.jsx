export default function ReportPanel({ report }) {
  if (!report) return null;

  return (
    <section className="panel" id="report-panel">
      <h2>6. Session report</h2>
      <div id="report-body">
        <p>
          <strong>{report.ai_label}</strong> — one clearly-labeled AI assistant. No attendance
          figures are recorded or reported.
        </p>
        <p>
          <strong>Unit:</strong> {report.unit_name}
          <br />
          <strong>Start:</strong> {report.started_at_iso}
          <br />
          <strong>End:</strong> {report.ended_at_iso}
          <br />
          <strong>Duration:</strong> {report.duration_minutes} minutes
        </p>

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
                [{q.timestamp_iso}] {q.question} <em>({q.trigger_reason})</em>
              </li>
            ))
          ) : (
            <li>(no questions were generated this session)</li>
          )}
        </ul>

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
