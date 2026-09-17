"""Pacing gate: decides whether it's time to fire a new question.

Trigger fires when EITHER:
  - silence_seconds have passed since the last transcript speech was seen, OR
  - max_interval_seconds have passed since the last question was shown
whichever comes first.

The silence trigger only fires once per silence gap: after a question is
shown, last_question_at moves ahead of last_speech_at, which blocks the
silence trigger from refiring on the *same* gap until new speech updates
last_speech_at again.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import config


@dataclass
class PacingDecision:
    triggered: bool
    reason: Optional[str] = None  # "silence" | "interval" | None


class PacingGate:
    def __init__(
        self,
        session_start: float,
        silence_seconds: int = config.PACING_SILENCE_SECONDS,
        max_interval_seconds: int = config.PACING_MAX_INTERVAL_SECONDS,
    ):
        self.silence_seconds = silence_seconds
        self.max_interval_seconds = max_interval_seconds
        self.last_question_at = session_start
        self.last_speech_at = session_start

    def note_speech(self, when: float) -> None:
        self.last_speech_at = max(self.last_speech_at, when)

    def note_question_shown(self, when: float) -> None:
        self.last_question_at = when

    def check(self, now: float) -> PacingDecision:
        if now - self.last_question_at >= self.max_interval_seconds:
            return PacingDecision(True, "interval")
        if (
            self.last_speech_at >= self.last_question_at
            and now - self.last_speech_at >= self.silence_seconds
        ):
            return PacingDecision(True, "silence")
        return PacingDecision(False, None)
