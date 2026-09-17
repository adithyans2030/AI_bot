"""Grok-backed question generation, grounded in retrieved unit chunks."""
from __future__ import annotations

from typing import List

from openai import OpenAI

from . import config
from .retrieval import ScoredChunk

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.XAI_API_KEY, base_url=config.XAI_BASE_URL)
    return _client


SYSTEM_PROMPT = (
    "You generate ONE plausible student question for a college doubt-clearing "
    "session. You are standing in for the students who didn't ask anything, "
    "not for the teacher. Rules:\n"
    "1. The question must be grounded in the provided unit material — don't "
    "invent facts outside it.\n"
    "2. Don't ask something the transcript already directly answered.\n"
    "3. Sound like a real student thinking out loud, not a textbook or exam "
    "question. Casual register, first person is fine (e.g. \"Wait, so...\", "
    "\"I'm a bit confused about...\").\n"
    "4. Output ONLY the question itself. No preamble, no quotes, no labels, "
    "no explanation."
)


def build_user_prompt(chunks: List[ScoredChunk], transcript_window: str) -> str:
    chunks_block = "\n\n".join(f"[Chunk {c.chunk_id}]\n{c.text}" for c in chunks) or "(none retrieved)"
    transcript_block = transcript_window.strip() or "(no recent transcript)"
    return (
        f"Relevant unit material:\n{chunks_block}\n\n"
        f"Recent transcript of what the teacher has been saying:\n{transcript_block}\n\n"
        "Generate one student question now."
    )


def generate_question(chunks: List[ScoredChunk], transcript_window: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=config.XAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(chunks, transcript_window)},
        ],
        temperature=0.8,
        max_tokens=120,
    )
    return response.choices[0].message.content.strip()
