"""Pacing gate: decides whether it's time to fire a new question.

Trigger fires when EITHER:
  - silence_seconds have passed since the last transcript speech was seen, OR
  - max_interval_seconds have passed since the last question was shown
whichever comes first — unless someone in the class (not the teacher) was
heard within the last participant_hold_seconds, in which case nothing fires:
a real student always takes priority over the AI.

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
        participant_hold_seconds: Optional[int] = None,
    ):
        self.silence_seconds = silence_seconds
        self.max_interval_seconds = max_interval_seconds
        # Read at construction (not as a default argument) so it follows
        # the current config, including in tests.
        self.participant_hold_seconds = (
            participant_hold_seconds if participant_hold_seconds is not None else config.PARTICIPANT_HOLD_SECONDS
        )
        self.last_question_at = session_start
        self.last_speech_at = session_start
        self.last_participant_at: Optional[float] = None

    def note_speech(self, when: float) -> None:
        self.last_speech_at = max(self.last_speech_at, when)

    def note_participant_speech(self, when: float) -> None:
        """Someone in the class (not the teacher) was heard. Counts as
        speech for the silence timer, and holds every trigger for
        participant_hold_seconds: a real student always takes priority."""
        self.last_participant_at = when if self.last_participant_at is None else max(self.last_participant_at, when)
        self.note_speech(when)

    def participant_recently_active(self, now: float) -> bool:
        return self.last_participant_at is not None and now - self.last_participant_at < self.participant_hold_seconds

    def note_question_shown(self, when: float) -> None:
        self.last_question_at = when

    def check(self, now: float) -> PacingDecision:
        if self.participant_recently_active(now):
            return PacingDecision(False, None)
        if now - self.last_question_at >= self.max_interval_seconds:
            return PacingDecision(True, "interval")
        if (
            self.last_speech_at >= self.last_question_at
            and now - self.last_speech_at >= self.silence_seconds
        ):
            return PacingDecision(True, "silence")
        return PacingDecision(False, None)
