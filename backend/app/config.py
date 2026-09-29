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

# --- Pacing gate ---
PACING_SILENCE_SECONDS = int(os.environ.get("PACING_SILENCE_SECONDS", "12"))
PACING_MAX_INTERVAL_SECONDS = int(os.environ.get("PACING_MAX_INTERVAL_SECONDS", "240"))

# --- Storage ---
DATA_DIR = BACKEND_DIR / "data"
UNITS_DIR = DATA_DIR / "units"
SESSIONS_DIR = DATA_DIR / "sessions"

# --- Identity guardrail ---
# Always use this label for the AI in UI copy, prompts, and logs. Never
# "Student", never a human name.
AI_LABEL = "AI Co-host (assistant, not a student)"
