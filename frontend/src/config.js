// Frontend-side tunables, mirroring the pattern in backend/app/config.py:
// one place, not scattered across components.

// How often we ask the backend "is it time for a question?"
export const TICK_POLL_MS = 5000;

// How often a slide frame is captured and sent while "Share slide" is on.
// Kept in seconds (not ms) to match the backend's SLIDE_CAPTURE_INTERVAL_SECONDS
// (app/config.py) at a glance — convert to ms only where actually used.
export const SLIDE_CAPTURE_INTERVAL_SECONDS = 10;
