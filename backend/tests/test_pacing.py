from app.pacing import PacingGate


def test_no_trigger_immediately_after_start():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240)
    decision = gate.check(now=1)
    assert decision.triggered is False


def test_silence_trigger_fires_after_threshold_with_no_speech():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240)
    decision = gate.check(now=13)
    assert decision.triggered is True
    assert decision.reason == "silence"


def test_silence_trigger_fires_after_gap_following_speech():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240)
    gate.note_speech(20)
    assert gate.check(now=25).triggered is False  # only 5s silence so far
    decision = gate.check(now=33)  # 13s since last speech
    assert decision.triggered is True
    assert decision.reason == "silence"


def test_silence_trigger_does_not_refire_on_same_gap():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240)
    gate.note_speech(20)
    decision = gate.check(now=33)
    assert decision.triggered is True
    gate.note_question_shown(33)
    # Still no new speech -> should NOT refire even much later, until interval cap.
    decision2 = gate.check(now=50)
    assert decision2.triggered is False


def test_silence_trigger_refires_after_new_speech():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240)
    gate.note_speech(20)
    gate.check(now=33)
    gate.note_question_shown(33)
    gate.note_speech(40)  # teacher speaks again
    decision = gate.check(now=53)  # 13s silence since new speech
    assert decision.triggered is True
    assert decision.reason == "silence"


def test_interval_trigger_fires_during_continuous_speech():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240)
    # Continuous speech keeps resetting the silence clock.
    for t in range(0, 241, 5):
        gate.note_speech(t)
    decision = gate.check(now=240)
    assert decision.triggered is True
    assert decision.reason == "interval"


def test_no_more_than_one_question_per_interval_during_continuous_speech():
    gate = PacingGate(session_start=0, silence_seconds=12, max_interval_seconds=240)
    fired_at = []
    for t in range(0, 900, 5):
        gate.note_speech(t)
        decision = gate.check(now=t)
        if decision.triggered:
            fired_at.append(t)
            gate.note_question_shown(t)
    # Over 900s with a 240s cap, expect roughly 900/240 ~ 3-4 fires, never more
    # often than every 240s.
    for a, b in zip(fired_at, fired_at[1:]):
        assert b - a >= 240
