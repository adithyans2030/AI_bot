// Thin fetch wrapper for the FastAPI backend. Same-origin in production
// (FastAPI serves the built app); proxied by Vite in dev (see vite.config.js).

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const get = (path) => request(path);

export const api = {
  listUnits: () => get("/units"),
  createUnit: (name, text) => post("/units", { name, text }),

  startSession: (unitId) => post("/sessions", { unit_id: unitId }),
  postTranscript: (sessionId, text, timestamp) =>
    post(`/sessions/${sessionId}/transcript`, { text, timestamp }),
  tick: (sessionId, force = false) => post(`/sessions/${sessionId}/tick`, { force }),
  addNote: (sessionId, text) => post(`/sessions/${sessionId}/note`, { text }),
  endSession: (sessionId) => post(`/sessions/${sessionId}/end`),
};
