import { useState } from "react";
import { api } from "../api.js";

export default function UnitPanel({ units, selectedUnitId, setSelectedUnitId, reloadUnits }) {
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!name.trim() || !text.trim()) {
      setStatus("Enter both a unit name and some notes.");
      return;
    }
    setSaving(true);
    setStatus("Chunking + embedding...");
    try {
      const unit = await api.createUnit(name.trim(), text.trim());
      setStatus(`Saved "${unit.name}" — ${unit.num_chunks} chunks.`);
      setName("");
      setText("");
      await reloadUnits();
      setSelectedUnitId(unit.id);
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel" id="unit-panel">
      <h2>1. Unit material</h2>
      <label>Unit name</label>
      <input
        type="text"
        placeholder="e.g. Unit 3 — Binary Search Trees"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <label>Notes / past questions (plain text)</label>
      <textarea
        rows={8}
        placeholder="Paste the unit's notes here..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button onClick={handleSave} disabled={saving}>
        Save unit material
      </button>
      <div className="status-line">{status}</div>

      <label>Existing units</label>
      <div className="row">
        <select value={selectedUnitId} onChange={(e) => setSelectedUnitId(e.target.value)}>
          {units.length === 0 && <option disabled>(no units saved yet)</option>}
          {units.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name} ({u.num_chunks} chunks)
            </option>
          ))}
        </select>
        <button className="secondary" onClick={reloadUnits}>
          Refresh
        </button>
      </div>
    </section>
  );
}
