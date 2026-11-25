// Thin fetch wrapper for the FastAPI backend. Same-origin in production
// (FastAPI serves the built app); proxied by Vite in dev (see vite.config.js).

// Signed-in session token from a Moodle LTI launch. The backend redirects
// to /app#token=..., the token is moved into sessionStorage (scoped to this
// browser tab, gone when it closes) and stripped from the address bar.
const TOKEN_KEY = "cohost_token";

export function captureTokenFromUrl() {
  const match = window.location.hash.match(/(?:^#|&)token=([^&]+)/);
  if (!match) return;
  sessionStorage.setItem(TOKEN_KEY, decodeURIComponent(match[1]));
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

function authHeaders() {
  const token = sessionStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...(options.headers || {}) },
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("Your sign-in has expired. Open AI Co-host again from your Moodle course.");
    }
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const get = (path) => request(path);

export const api = {
  me: () => get("/auth/me"),

  listUnits: () => get("/units"),
  createUnit: (name, text) => post("/units", { name, text }),

  startSession: (unitId) => post("/sessions", { unit_id: unitId }),
  postTranscript: (sessionId, text, timestamp) =>
    post(`/sessions/${sessionId}/transcript`, { text, timestamp }),
  // "Someone in the class is speaking" — no audio or words are sent.
  postParticipantActivity: (sessionId) => post(`/sessions/${sessionId}/activity`),
  tick: (sessionId, force = false) => post(`/sessions/${sessionId}/tick`, { force }),
  postFrame: (sessionId, frame) => post(`/sessions/${sessionId}/frame`, { frame }),
  wrapUp: (sessionId) => post(`/sessions/${sessionId}/wrap-up`),
  addNote: (sessionId, text) => post(`/sessions/${sessionId}/note`, { text }),
  endSession: (sessionId) => post(`/sessions/${sessionId}/end`),
};
