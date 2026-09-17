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

# --- xAI (Grok) ---
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-fast-non-reasoning")

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
