"""Human priority: a real student speaking always beats the AI.

Two layers: the pacing gate holds every trigger while someone in the class
was heard recently, and tick() drops a question that finished generating
after a student started speaking.
"""
from __future__ import annotations

from app import session_manager, storage
from app.pacing import PacingGate

from tests.test_tick_guardrails import BST_TEXT, _cleanup, _make_runtime


def test_participant_speech_holds_interval_trigger():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240, participant_hold_seconds=15)
    gate.note_participant_speech(290)
    assert gate.check(300).triggered is False  # interval long passed, but a student just spoke
    assert gate.check(306).triggered is True  # hold over (16 s after they spoke)


def test_participant_speech_resets_the_silence_timer():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240, participant_hold_seconds=15)
    gate.note_speech(10)
    assert gate.check(23).triggered is True  # 13 s of silence after the teacher
    gate.note_participant_speech(20)
    assert gate.check(30).triggered is False  # a student spoke 10 s ago
    decision = gate.check(36)
    assert decision.triggered is True and decision.reason == "silence"


def test_no_participant_activity_behaves_exactly_as_before():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240, participant_hold_seconds=15)
    assert gate.participant_recently_active(1000) is False
    assert gate.check(13).reason == "silence"


def test_tick_holds_while_a_student_is_speaking(monkeypatch):
    runtime = _make_runtime("priority-1")
    try:
        runtime.session["transcript"] = [{"text": BST_TEXT, "timestamp": 290}]
        monkeypatch.setattr(session_manager.question_gen, "generate_question", lambda *a, **k: "Q")
        session_manager.note_participant_activity("priority-1", timestamp=295)
        assert session_manager.tick("priority-1", now=300) == {"triggered": False}
    finally:
        _cleanup("priority-1")


def test_question_is_dropped_if_a_student_starts_speaking_during_generation(monkeypatch):
    runtime = _make_runtime("priority-2")
    try:
        runtime.session["transcript"] = [{"text": BST_TEXT, "timestamp": 290}]

        def generate_while_student_speaks(*a, **k):
            session_manager.note_participant_activity("priority-2", timestamp=301)
            return "A question nobody should hear"

        monkeypatch.setattr(session_manager.question_gen, "generate_question", generate_while_student_speaks)
        result = session_manager.tick("priority-2", now=300)

        assert result == {"triggered": False, "reason": "participant_spoke"}
        log_types = [e["type"] for e in runtime.session["log"]]
        assert "question_generated" not in log_types
        assert "question_suppressed" in log_types
        # The gate was not advanced and coverage not credited.
        assert runtime.pacing.last_question_at == 0
        assert runtime.asked_chunk_ids == set()
    finally:
        _cleanup("priority-2")


def test_manual_force_question_is_not_dropped(monkeypatch):
    runtime = _make_runtime("priority-3")
    try:
        runtime.session["transcript"] = [{"text": BST_TEXT, "timestamp": 290}]

        def generate_while_student_speaks(*a, **k):
            session_manager.note_participant_activity("priority-3", timestamp=301)
            return "Teacher asked for this one"

        monkeypatch.setattr(session_manager.question_gen, "generate_question", generate_while_student_speaks)
        result = session_manager.tick("priority-3", now=300, force=True)
        assert result["triggered"] is True
    finally:
        _cleanup("priority-3")


def test_participant_activity_is_never_persisted_or_reported(monkeypatch):
    runtime = _make_runtime("priority-4")
    runtime.session.update(
        {"unit_id": "u", "unit_name": "BST", "started_at": 0, "ended_at": None, "ai_label": "AI", "total_chunks": 1}
    )
    try:
        session_manager.note_participant_activity("priority-4", timestamp=50)
        storage.save_session(runtime.session)
        saved = storage.load_session("priority-4")
        assert "participant" not in str(saved).lower()
        report = session_manager.get_report("priority-4")
        assert "participant" not in str(report).lower()
    finally:
        _cleanup("priority-4")
