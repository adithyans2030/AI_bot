import { useState } from "react";

function fmtTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

export default function NotesPanel({ session, entries, onAddNote }) {
  const [text, setText] = useState("");

  function handleAdd() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onAddNote(trimmed);
    setText("");
  }

  return (
    <section className="panel" id="notes-panel">
      <h2>5. Teacher notes (optional)</h2>
      <div className="row">
        <textarea
          rows={2}
          placeholder="Brief note about what was answered..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button className="secondary" onClick={handleAdd} disabled={!session}>
          Add note
        </button>
      </div>
      <div className="scroll-box">
        {entries.map((n, i) => (
          <div className="log-entry" key={i}>
            <span className="ts">{fmtTime(n.timestamp)}</span>
            {n.text}
          </div>
        ))}
      </div>
    </section>
  );
}
