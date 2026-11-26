"""The AI controller: the LLM proposes, code disposes.

The LLM call (controller.decide's model request) is always stubbed, so
these tests pin down what code guarantees no matter what the model says:
when it is consulted, what it is allowed to do, what happens when it fails,
and that off-topic questions never reach the class.
"""
from __future__ import annotations

import pytest

from app import config, controller, session_manager, storage
from app.controller import Decision, Observation

from tests.test_tick_guardrails import BST_TEXT, _cleanup, _make_runtime

ON_TOPIC = "Wait, how does search in a binary search tree decide whether to go left or right?"
OFF_TOPIC = "What were the main causes of the French Revolution?"


@pytest.fixture(autouse=True)
def agent_mode(monkeypatch):
    monkeypatch.setattr(config, "CONTROLLER_MODE", "agent")


def _obs(**overrides) -> Observation:
    values = dict(
        elapsed_minutes=20,
        minutes_remaining=40,
        silence_seconds=10,
        seconds_since_last_question=300,
        questions_asked=1,
        questions_last_hour=1,
        coverage_ratio=0.2,
        recent_transcript="so that is how insertion works",
    )
    values.update(overrides)
    return Observation(**values)


def _stub_decide(monkeypatch, action=None, reason="test reason"):
    """Replace the LLM decision. action=None simulates an unavailable model."""
    calls = {"n": 0, "obs": None}

    def fake(obs):
        calls["n"] += 1
        calls["obs"] = obs
        return Decision(action, reason, "agent") if action else None

    monkeypatch.setattr(controller, "decide", fake)
    return calls


def _stub_generate(monkeypatch, text=ON_TOPIC):
    calls = {"n": 0, "kwargs": None}

    def fake(*args, **kwargs):
        calls["n"] += 1
        calls["kwargs"] = kwargs
        return text

    monkeypatch.setattr(session_manager.question_gen, "generate_question", fake)
    return calls


def _quiet_runtime(session_id, **session_fields):
    """A session 5 min in, teacher spoke 10 s ago about BSTs, last question
    long ago: a moment where the controller should be consulted."""
    runtime = _make_runtime(session_id)
    runtime.session["transcript"] = [{"text": BST_TEXT, "timestamp": 290}]
    runtime.pacing.note_speech(290)
    runtime.session.update(session_fields)
    return runtime


# --- Parsing the model's reply ---


@pytest.mark.parametrize(
    "reply, action",
    [
        ('{"action": "ask_question", "reason": "Teacher asked for doubts."}', "ask_question"),
        ('```json\n{"action": "stay_silent", "reason": "Mid-explanation."}\n```', "stay_silent"),
        ('Sure! {"action": "ASK_THE_CLASS", "reason": "Long quiet."} Hope that helps.', "ask_the_class"),
    ],
)
def test_parse_decision_accepts_valid_replies(reply, action):
    decision = controller.parse_decision(reply)
    assert decision is not None and decision.action == action and decision.source == "agent"


@pytest.mark.parametrize(
    "reply",
    ["", "ask a question now", '{"action": "end_class"}', '{"action": ', "[1, 2]", '{"reason": "no action"}'],
)
def test_parse_decision_rejects_unusable_replies(reply):
    assert controller.parse_decision(reply) is None


# --- Code checks before the AI is consulted ---


@pytest.mark.parametrize(
    "kwargs, obs_overrides, expected",
    [
        ({"paused": True}, {}, "paused"),
        ({"student_speaking": True}, {}, "student_speaking"),
        ({}, {"has_content": False}, "no_content"),
        ({}, {"seconds_since_last_question": 30}, "cooldown"),
        ({}, {"questions_last_hour": 6}, "budget"),
        ({}, {"silence_seconds": 2, "seconds_since_last_question": 120}, "teacher_speaking"),
        ({"seconds_since_last_decision": 5}, {}, "recently_decided"),
    ],
)
def test_precheck_blocks_without_consulting_the_ai(kwargs, obs_overrides, expected):
    args = {"paused": False, "student_speaking": False, "seconds_since_last_decision": None}
    args.update(kwargs)
    assert controller.precheck(_obs(**obs_overrides), **args) == expected


def test_precheck_allows_a_quiet_moment():
    assert controller.precheck(_obs(), paused=False, student_speaking=False, seconds_since_last_decision=None) is None


def test_precheck_allows_consulting_during_a_long_stretch_of_teacher_talk():
    obs = _obs(silence_seconds=1, seconds_since_last_question=config.PACING_MAX_INTERVAL_SECONDS + 1)
    assert controller.precheck(obs, paused=False, student_speaking=False, seconds_since_last_decision=None) is None


# --- Code checks after the AI chooses ---


def test_validate_vetoes_early_wrap_up():
    decision = controller.validate(Decision(controller.RUN_WRAP_UP, "r", "agent"), _obs(minutes_remaining=30))
    assert decision.action == controller.STAY_SILENT and decision.source == "guardrail"


def test_validate_vetoes_second_wrap_up():
    decision = controller.validate(
        Decision(controller.RUN_WRAP_UP, "r", "agent"), _obs(minutes_remaining=5, wrap_up_done=True)
    )
    assert decision.action == controller.STAY_SILENT


def test_validate_allows_wrap_up_near_the_end():
    proposed = Decision(controller.RUN_WRAP_UP, "r", "agent")
    assert controller.validate(proposed, _obs(minutes_remaining=5)) is proposed


def test_user_prompt_carries_the_moment():
    prompt = controller.build_user_prompt(_obs(slide_title="BST deletion", recently_asked=["search cost"]))
    assert "BST deletion" in prompt and "search cost" in prompt and "insertion" in prompt


# --- The agent loop end to end (LLM stubbed) ---


def test_ai_chooses_silence(monkeypatch):
    runtime = _quiet_runtime("agent-1")
    try:
        decide = _stub_decide(monkeypatch, controller.STAY_SILENT, "Teacher is mid-explanation.")
        generate = _stub_generate(monkeypatch)
        result = session_manager.tick("agent-1", now=300)
        assert result["triggered"] is False
        assert result["agent"] == {"action": "stay_silent", "reason": "Teacher is mid-explanation.", "source": "agent"}
        assert decide["n"] == 1 and generate["n"] == 0
        assert [e["action"] for e in runtime.session["log"] if e["type"] == "agent_decision"] == ["stay_silent"]
    finally:
        _cleanup("agent-1")


def test_ai_asks_a_grounded_question(monkeypatch):
    runtime = _quiet_runtime("agent-2", unit_id="u", unit_name="BST", started_at=0, ended_at=None, ai_label="AI", total_chunks=1)
    try:
        _stub_decide(monkeypatch, controller.ASK_QUESTION, "The teacher just finished explaining search.")
        _stub_generate(monkeypatch, ON_TOPIC)
        result = session_manager.tick("agent-2", now=300)
        assert result["triggered"] is True
        assert result["question"] == ON_TOPIC
        assert result["reason"] == "agent:ask_question"
        assert result["audience"] == "teacher"
        assert result["agent"]["reason"] == "The teacher just finished explaining search."

        report = session_manager.get_report("agent-2")
        assert report["questions"][0]["agent_reason"] == "The teacher just finished explaining search."
        assert report["ai_decisions"]["consulted"] == 1
        assert report["ai_decisions"]["by_action"] == {"ask_question": 1}
    finally:
        _cleanup("agent-2")


def test_ask_the_class_uses_the_class_prompt(monkeypatch):
    _quiet_runtime("agent-3")
    try:
        _stub_decide(monkeypatch, controller.ASK_THE_CLASS, "Quiet for a long time.")
        generate = _stub_generate(monkeypatch, "Can someone explain how search in a binary search tree picks a direction?")
        result = session_manager.tick("agent-3", now=300)
        assert result["triggered"] is True and result["audience"] == "class"
        assert generate["kwargs"]["audience"] == "class"
    finally:
        _cleanup("agent-3")


def test_off_topic_question_is_dropped(monkeypatch):
    runtime = _quiet_runtime("agent-4")
    try:
        _stub_decide(monkeypatch, controller.ASK_QUESTION, "Good moment.")
        _stub_generate(monkeypatch, OFF_TOPIC)
        result = session_manager.tick("agent-4", now=300)
        assert result == {"triggered": False, "reason": "not_grounded", "agent": result["agent"]}
        assert not [e for e in runtime.session["log"] if e["type"] == "question_generated"]
        rejected = [e for e in runtime.session["log"] if e["type"] == "question_rejected"]
        assert rejected and rejected[0]["grounding_score"] < config.MIN_GROUNDING_SCORE
        assert runtime.question_times == []  # doesn't use up the budget
    finally:
        _cleanup("agent-4")


def test_unavailable_ai_falls_back_to_the_pacing_rules(monkeypatch):
    _quiet_runtime("agent-5")
    try:
        _stub_decide(monkeypatch, action=None)
        _stub_generate(monkeypatch, ON_TOPIC)
        # now=300: past the 240 s interval, so the rules gate fires.
        result = session_manager.tick("agent-5", now=300)
        assert result["triggered"] is True
        assert result["agent"]["source"] == "fallback"
    finally:
        _cleanup("agent-5")


def test_unavailable_ai_and_quiet_rules_means_silence(monkeypatch):
    runtime = _quiet_runtime("agent-6")
    try:
        runtime.pacing.note_question_shown(150)  # rules gate: 150 s since last question, < 240
        runtime.pacing.note_speech(292)  # 8 s of silence: enough to consult, not enough for the rules
        _stub_decide(monkeypatch, action=None)
        generate = _stub_generate(monkeypatch)
        result = session_manager.tick("agent-6", now=300)
        assert result["triggered"] is False and result["agent"]["source"] == "fallback"
        assert generate["n"] == 0
    finally:
        _cleanup("agent-6")


def test_ai_is_not_consulted_while_teacher_talks_or_too_often(monkeypatch):
    runtime = _quiet_runtime("agent-7")
    try:
        decide = _stub_decide(monkeypatch, controller.STAY_SILENT, "Wait.")
        _stub_generate(monkeypatch)
        runtime.pacing.note_question_shown(200)  # recent enough that only silence can open a decision

        runtime.pacing.note_speech(299)  # teacher talking right now
        assert session_manager.tick("agent-7", now=300)["reason"] == "teacher_speaking"
        assert decide["n"] == 0

        assert session_manager.tick("agent-7", now=310)["agent"]["source"] == "agent"  # 11 s quiet: consulted
        assert session_manager.tick("agent-7", now=315)["reason"] == "recently_decided"  # 5 s later: not again
        assert decide["n"] == 1
    finally:
        _cleanup("agent-7")


def test_budget_and_pause_stop_the_ai_without_consulting_it(monkeypatch):
    runtime = _quiet_runtime("agent-8")
    try:
        decide = _stub_decide(monkeypatch, controller.ASK_QUESTION, "Go.")
        _stub_generate(monkeypatch)

        runtime.question_times = [10, 20, 30, 40, 50, 60]  # 6 in the last hour
        assert session_manager.tick("agent-8", now=300)["reason"] == "budget"

        runtime.question_times = []
        session_manager.set_paused("agent-8", True)
        assert session_manager.tick("agent-8", now=300)["reason"] == "paused"
        assert decide["n"] == 0
        # The teacher's manual button still works while paused.
        assert session_manager.tick("agent-8", now=300, force=True)["triggered"] is True

        log_types = [e["type"] for e in runtime.session["log"]]
        assert "cohost_paused" in log_types
    finally:
        _cleanup("agent-8")


def test_student_speaking_blocks_the_ai(monkeypatch):
    _quiet_runtime("agent-9")
    try:
        decide = _stub_decide(monkeypatch, controller.ASK_QUESTION, "Go.")
        session_manager.note_participant_activity("agent-9", timestamp=295)
        assert session_manager.tick("agent-9", now=300)["reason"] == "student_speaking"
        assert decide["n"] == 0
    finally:
        _cleanup("agent-9")


def test_wrap_up_runs_once_near_the_end(monkeypatch):
    # 300 s into a 10-minute class: 5 min left, inside the wrap-up window.
    runtime = _quiet_runtime("agent-10", class_minutes=10)
    try:
        _stub_decide(monkeypatch, controller.RUN_WRAP_UP, "Class is ending.")
        _stub_generate(monkeypatch, "Before we wrap up, could you go over how search works in a binary search tree?")
        result = session_manager.tick("agent-10", now=300)
        assert result["triggered"] is True and result["wrap_up"] is True
        assert result["reason"] == "agent:run_wrap_up"
        assert runtime.agent_wrap_up_done is True

        # A later wrap-up choice is vetoed by code.
        runtime.last_decision_at = None
        runtime.pacing.note_speech(500)
        vetoed = session_manager.tick("agent-10", now=510)
        assert vetoed["triggered"] is False
        assert vetoed["agent"]["source"] == "guardrail"
    finally:
        _cleanup("agent-10")


def test_early_wrap_up_is_vetoed_and_logged(monkeypatch):
    runtime = _quiet_runtime("agent-11", class_minutes=60)
    try:
        _stub_decide(monkeypatch, controller.RUN_WRAP_UP, "Feels like the end.")
        generate = _stub_generate(monkeypatch)
        result = session_manager.tick("agent-11", now=300)
        assert result["triggered"] is False and result["agent"]["source"] == "guardrail"
        assert generate["n"] == 0
        veto = [e for e in runtime.session["log"] if e["type"] == "agent_veto"]
        assert veto and veto[0]["proposed_action"] == "run_wrap_up"
    finally:
        _cleanup("agent-11")


def test_rules_mode_is_unchanged(monkeypatch):
    monkeypatch.setattr(config, "CONTROLLER_MODE", "rules")
    _quiet_runtime("agent-12")
    try:
        decide = _stub_decide(monkeypatch, controller.STAY_SILENT)
        _stub_generate(monkeypatch, ON_TOPIC)
        result = session_manager.tick("agent-12", now=300)
        assert result["triggered"] is True and result["reason"] in {"interval", "silence"}
        assert "agent" not in result
        assert decide["n"] == 0
    finally:
        _cleanup("agent-12")


def test_pause_endpoint_and_health(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/health").json()["controller_mode"] == "agent"
    _quiet_runtime("agent-13")
    try:
        assert client.post("/sessions/agent-13/pause", json={"paused": True}).json() == {"paused": True}
        assert session_manager.ACTIVE_SESSIONS["agent-13"].paused is True
        assert client.post("/sessions/agent-13/pause", json={"paused": False}).json() == {"paused": False}
    finally:
        _cleanup("agent-13")
        path = storage.session_path("agent-13")
        if path.exists():
            path.unlink()
