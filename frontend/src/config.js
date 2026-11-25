// Frontend-side tunables, mirroring the pattern in backend/app/config.py:
// one place, not scattered across components.

// How often we ask the backend "is it time for a question?"
export const TICK_POLL_MS = 5000;

// How often a slide frame is captured and sent while "Share slide" is on.
// Kept in seconds (not ms) to match the backend's SLIDE_CAPTURE_INTERVAL_SECONDS
// (app/config.py) at a glance — convert to ms only where actually used.
export const SLIDE_CAPTURE_INTERVAL_SECONDS = 10;

// Human priority — detecting class members speaking in the shared Meet tab.
// Audio level (RMS, 0-1) above which a frame counts as speech. Tune in a
// real class: too low and background noise holds questions back, too high
// and quiet students are missed.
export const VAD_RMS_THRESHOLD = 0.02;
// Sound must last at least this long to count (filters chimes and clicks).
export const VAD_MIN_SPEECH_MS = 300;
// While someone keeps talking, tell the backend at most this often.
export const ACTIVITY_POST_THROTTLE_MS = 2000;
