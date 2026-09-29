import { useState } from "react";

function fmtTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

export default function NotesPanel({ session, entries, onAddNote }) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(true);

  function handleAdd() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onAddNote(trimmed);
    setText("");
  }

  return (
    <section className="panel" id="notes-panel">
      <button className="collapsible-header" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <h2>Teacher notes (optional)</h2>
        <span className="chevron">{open ? "–" : "+"}</span>
      </button>

      {open && (
        <div className="collapsible-body">
          <label htmlFor="note-input">Add a note</label>
          <div className="row">
            <textarea
              id="note-input"
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
            {entries.length === 0 && <div className="empty-hint">No notes added.</div>}
            {entries.map((n, i) => (
              <div className="log-entry" key={i}>
                <span className="ts">{fmtTime(n.timestamp)}</span>
                {n.text}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
