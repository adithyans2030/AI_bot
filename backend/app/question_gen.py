"""Local-LLM-backed question generation, grounded in retrieved unit chunks.

Uses the `openai` package pointed at a local Ollama server's OpenAI-compatible
endpoint, so no extra dependency is needed and no API key/credits/account is
required. Swapping to a different OpenAI-compatible backend (cloud or local)
is just a config change — see config.py.
"""
from __future__ import annotations

from typing import List, Optional

from openai import OpenAI

from . import config
from .retrieval import ScoredChunk

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
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


def build_user_prompt(
    chunks: List[ScoredChunk],
    transcript_window: str,
    slide_text: Optional[str] = None,
    previously_asked_previews: Optional[List[str]] = None,
    wrap_up: bool = False,
) -> str:
    chunks_block = "\n\n".join(f"[Chunk {c.chunk_id}]\n{c.text}" for c in chunks) or "(none retrieved)"
    transcript_block = transcript_window.strip() or "(no recent transcript)"
    slide_block = (
        f"\n\nCurrently visible on the shared slide:\n{slide_text.strip()}" if slide_text and slide_text.strip() else ""
    )
    # Omitted entirely when empty (session start) — "Questions already
    # asked: (none)" wastes tokens and adds no signal.
    asked_block = (
        "\n\nQuestions already asked this session (don't repeat these):\n"
        + "\n".join(f"- {preview}" for preview in previously_asked_previews)
        if previously_asked_previews
        else ""
    )
    wrap_up_block = (
        "\n\nThis is an end-of-session wrap-up moment, not a normal "
        "mid-lecture interruption — phrase it as a gentle nudge toward "
        "something not yet covered, e.g. \"Before we wrap up, some of you "
        "might still be wondering about...\"."
        if wrap_up
        else ""
    )
    return (
        f"Relevant unit material:\n{chunks_block}\n\n"
        f"Recent transcript of what the teacher has been saying:\n{transcript_block}"
        f"{slide_block}{asked_block}{wrap_up_block}\n\n"
        "Generate one student question now."
    )


def generate_question(
    chunks: List[ScoredChunk],
    transcript_window: str,
    slide_text: Optional[str] = None,
    previously_asked_previews: Optional[List[str]] = None,
    wrap_up: bool = False,
) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(
                    chunks, transcript_window, slide_text, previously_asked_previews, wrap_up
                ),
            },
        ],
        temperature=0.8,
        max_tokens=120,
    )
    return response.choices[0].message.content.strip()
