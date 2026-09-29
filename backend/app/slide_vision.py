"""Reads a shared slide from a single captured frame.

This is perception on an interval, not an agent: read_slide() answers "what
does this frame show right now" and nothing else. It never decides to do
anything — session_manager.py is the only place that acts on the result,
and only ever by feeding it into the existing retrieval/question-generation
pipeline, gated by the existing pacing logic. A slide read never triggers a
question by itself.

Uses the same local Ollama server as question_gen.py, just a smaller,
vision-capable model (see config.LLM_VISION_MODEL) — heavier per-call than
the text model, and called far more often (every ~10s of sharing vs. once
per question), so model size matters even more here.
"""
from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
from openai import OpenAI
from PIL import Image

from . import config

_client = None

# Small line-based format, not JSON: moondream-class models are basic
# image-captioning/VQA models, not strong instruction-followers, and
# reliably produce this far more often than valid JSON.
_VISION_PROMPT = (
    "Look at this image, which may be a shared presentation slide from a "
    "college lecture.\n\n"
    "If it looks like a slide with a title and some text, respond in "
    "exactly this format (three lines, nothing else):\n"
    "TITLE: <the slide's title>\n"
    "TEXT: <the main heading/bullet text visible, one line>\n"
    "CONFIDENCE: HIGH\n\n"
    "If it does NOT look like a slide (blank screen, video call layout, "
    "unrelated app, too blurry/unclear to read), respond in exactly this "
    "format instead:\n"
    "TITLE: NONE\n"
    "TEXT: NONE\n"
    "CONFIDENCE: LOW"
)

_TITLE_RE = re.compile(r"TITLE:\s*(.*)", re.IGNORECASE)
_TEXT_RE = re.compile(r"TEXT:\s*(.*)", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"CONFIDENCE:\s*(HIGH|LOW)", re.IGNORECASE)

_LOW_CONFIDENCE = {"slide_title": None, "key_text": None, "confidence": "low"}


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    return _client


def _as_data_url(frame: str) -> str:
    """Accepts either a raw base64 JPEG or an already-prefixed data URL."""
    if frame.startswith("data:image"):
        return frame
    return f"data:image/jpeg;base64,{frame}"


def _decode_to_bytes(frame: str) -> bytes:
    raw = frame.split(",", 1)[1] if frame.startswith("data:image") else frame
    return base64.b64decode(raw)


def frame_thumbnail(frame: str, size: int = 16) -> Optional[np.ndarray]:
    """Decode a frame (raw base64 or data URL) to a small grayscale
    thumbnail array, for cheap perceptual diffing. Returns None if the
    frame can't be decoded (never raises — a bad frame just means "treat
    as changed" upstream, not a crash)."""
    try:
        image = Image.open(io.BytesIO(_decode_to_bytes(frame)))
        image = image.convert("L").resize((size, size))
        return np.asarray(image, dtype=np.float32) / 255.0
    except Exception:
        return None


def thumbnail_diff(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    """Mean absolute pixel difference between two thumbnails, in [0, 1].
    Treats a missing thumbnail on either side as "maximally different" so
    a decode failure never accidentally causes an update to be skipped."""
    if a is None or b is None or a.shape != b.shape:
        return 1.0
    return float(np.mean(np.abs(a - b)))


def _parse_response(text: str) -> dict:
    confidence_match = _CONFIDENCE_RE.search(text)
    if not confidence_match or confidence_match.group(1).upper() != "HIGH":
        return dict(_LOW_CONFIDENCE)

    title_match = _TITLE_RE.search(text)
    text_match = _TEXT_RE.search(text)
    title = title_match.group(1).strip() if title_match else ""
    key_text = text_match.group(1).strip() if text_match else ""

    if not title and not key_text:
        return dict(_LOW_CONFIDENCE)

    return {
        "slide_title": title or None,
        "key_text": key_text or None,
        "confidence": "high",
    }


def read_slide(frame: str) -> dict:
    """Sends one frame to the local vision model and returns a structured
    read: {"slide_title": str|None, "key_text": str|None, "confidence": "high"|"low"}.

    Never raises: any failure (model not pulled, Ollama unreachable,
    unparseable response) degrades to a low-confidence result, which the
    caller discards rather than feeding a guess into topic matching.
    """
    try:
        client = get_client()
        response = client.chat.completions.create(
            model=config.LLM_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": _as_data_url(frame)}},
                    ],
                }
            ],
            temperature=0.2,
            max_tokens=120,
        )
        content = response.choices[0].message.content or ""
        return _parse_response(content)
    except Exception:
        return dict(_LOW_CONFIDENCE)
