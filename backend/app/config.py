"""Single source of truth for API keys, model names, and tunable thresholds.

Nothing outside this module should read os.environ directly or hardcode a
model name / threshold value.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

# --- Local LLM, via Ollama's OpenAI-compatible endpoint ---
# Runs fully on this machine: no API key, no credits, no account, no rate
# limits from a provider. Any other OpenAI-compatible local server (LM
# Studio, etc.) works too — just change LLM_BASE_URL.
# Ollama doesn't check the key at all; the OpenAI client just requires the
# field to be a non-empty string.
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
# Defaults to a small model on purpose: on a 4GB-VRAM GPU, a model that
# doesn't fit in VRAM spills into CPU/GPU split inference and gets ~15x
# slower (163s vs 11s, measured). Pick a bigger model here only if your
# hardware can actually hold it in VRAM.
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma2:2b")

# --- Slide vision (optional, only used when the teacher shares a slide) ---
# A separate, smaller model than LLM_MODEL — vision models are heavier
# per-parameter, and this call happens far more often (every ~10s of
# sharing vs. once per question), so it needs to be small enough to stay
# fast on the same GPU. moondream (~1.7GB) fits comfortably in 4GB VRAM;
# a 7B+ vision model like llava would spill into slow CPU/GPU split
# inference the same way llama3.1 did for text generation (see LLM_MODEL
# above) — verified that failure mode already, don't repeat it here.
LLM_VISION_MODEL = os.environ.get("LLM_VISION_MODEL", "moondream")

# How often the frontend samples a frame while a slide is being shared.
SLIDE_CAPTURE_INTERVAL_SECONDS = int(os.environ.get("SLIDE_CAPTURE_INTERVAL_SECONDS", "10"))
# A slide read older than this is considered stale (sharing likely
# stopped, or the frontend stopped sending frames) and topic matching
# falls back to transcript-only, exactly as if slide capture was never
# turned on.
SLIDE_STALENESS_SECONDS = int(os.environ.get("SLIDE_STALENESS_SECONDS", "30"))
# Skip the (comparatively expensive) vision call when the new frame's
# downscaled thumbnail is nearly identical to the last processed one —
# i.e. the slide hasn't visibly changed. 0.0 = identical thumbnails,
# larger = more different. This is a mean-pixel-difference on a 16x16
# grayscale thumbnail, normalized to [0, 1]; empirically, an actual slide
# change lands well above 0.05, minor re-encode/cursor noise stays well
# below it.
SLIDE_FRAME_DIFF_THRESHOLD = float(os.environ.get("SLIDE_FRAME_DIFF_THRESHOLD", "0.05"))

# --- Embeddings ---
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- Unit material chunking ---
CHUNK_MIN_WORDS = int(os.environ.get("CHUNK_MIN_WORDS", "150"))
CHUNK_MAX_WORDS = int(os.environ.get("CHUNK_MAX_WORDS", "300"))

# --- Retrieval ---
RETRIEVAL_TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", "3"))
MATCH_WINDOW_SECONDS = int(os.environ.get("MATCH_WINDOW_SECONDS", "90"))
# Coverage tracking: soft score penalty applied to a chunk already used for
# a fired question this session, so repeated pacing triggers on similar
# content don't just re-surface the same chunk (see SessionRuntime.asked_chunk_ids
# and retrieval.top_k_chunks in session_manager.py / retrieval.py).
COVERAGE_REPEAT_PENALTY = float(os.environ.get("COVERAGE_REPEAT_PENALTY", "0.15"))
# Above this fraction of unit chunks already covered, /wrap-up treats the
# session as sufficiently covered and returns a status line instead of
# generating more questions (session_manager.wrap_up).
COVERAGE_WRAP_UP_THRESHOLD = float(os.environ.get("COVERAGE_WRAP_UP_THRESHOLD", "0.8"))

# --- Pacing gate ---
PACING_SILENCE_SECONDS = int(os.environ.get("PACING_SILENCE_SECONDS", "12"))
PACING_MAX_INTERVAL_SECONDS = int(os.environ.get("PACING_MAX_INTERVAL_SECONDS", "240"))

# Human priority: when anyone in the class (not the teacher) is heard in the
# shared Meet tab's audio, hold off on firing a question for this many
# seconds — the agent only fills genuine silence, it never talks over a
# real student. Also discards a question that finished generating after a
# student started speaking. Participant activity is held in memory only and
# never logged or reported (no participation data, same guardrail as
# attendance).
PARTICIPANT_HOLD_SECONDS = int(os.environ.get("PARTICIPANT_HOLD_SECONDS", "15"))


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# --- Storage ---
DATA_DIR = BACKEND_DIR / "data"
UNITS_DIR = DATA_DIR / "units"
SESSIONS_DIR = DATA_DIR / "sessions"
LTI_DIR = DATA_DIR / "lti"

# --- Authentication (Moodle LTI 1.3) ---
# Off by default so local development and the test suite work without a
# Moodle. Turn on for any real deployment: every /units and /sessions route
# then requires a token issued by a successful Moodle LTI launch, and only
# teachers (Instructor / Administrator roles) get one.
AUTH_REQUIRED = _env_bool("AUTH_REQUIRED", False)
# Public base URL of this tool, exactly as Moodle reaches it (used to build
# the LTI redirect_uri). No trailing slash.
TOOL_BASE_URL = os.environ.get("TOOL_BASE_URL", "http://localhost:8000").rstrip("/")
# The Moodle site's wwwroot, e.g. https://onlinecourses.example.edu — this
# is the LTI "Platform ID" (issuer) Moodle shows after registering the tool.
LTI_PLATFORM_ISSUER = os.environ.get("LTI_PLATFORM_ISSUER", "").rstrip("/")
LTI_CLIENT_ID = os.environ.get("LTI_CLIENT_ID", "")
# Comma-separated: one tool registration can have several deployments.
LTI_DEPLOYMENT_IDS = [d.strip() for d in os.environ.get("LTI_DEPLOYMENT_IDS", "").split(",") if d.strip()]
# Moodle's standard LTI 1.3 endpoints, derived from the issuer unless overridden.
LTI_AUTH_LOGIN_URL = os.environ.get("LTI_AUTH_LOGIN_URL", f"{LTI_PLATFORM_ISSUER}/mod/lti/auth.php")
LTI_PLATFORM_KEYSET_URL = os.environ.get("LTI_PLATFORM_KEYSET_URL", f"{LTI_PLATFORM_ISSUER}/mod/lti/certs.php")
# The tool's own RSA key (served at /lti/jwks). Generated on first use if
# the file doesn't exist. Keep it out of git — it lives under data/lti/.
LTI_TOOL_PRIVATE_KEY_PATH = Path(os.environ.get("LTI_TOOL_PRIVATE_KEY_PATH", str(LTI_DIR / "tool_private_key.pem")))
# Secret for signing the app's own session tokens after a launch. If unset,
# one is generated and persisted under data/lti/ on first use.
APP_SECRET = os.environ.get("APP_SECRET", "")
# How long a teacher stays signed in after launching from Moodle.
APP_TOKEN_TTL_SECONDS = int(os.environ.get("APP_TOKEN_TTL_SECONDS", str(8 * 3600)))

# --- Identity guardrail ---
# Always use this label for the AI in UI copy, prompts, and logs. Never
# "Student", never a human name.
AI_LABEL = "AI Co-host (assistant, not a student)"
