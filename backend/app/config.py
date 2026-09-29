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
