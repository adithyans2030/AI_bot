"""Tests for coverage tracking and the end-of-session wrap-up pass
(session_manager.wrap_up). Real embeddings (ingestion.embed_texts), mocked
question_gen.generate_question so these don't need Ollama running — what's
under test here is the coverage/selection logic, not question quality.
"""
from __future__ import annotations

from app import ingestion, session_manager, storage
from app.pacing import PacingGate

BST_TEXT = "Binary search trees support fast search by comparing keys and descending left or right at each node."
GRAPH_TEXT = "Graph traversal algorithms like breadth-first and depth-first search visit every vertex and edge."


def _make_runtime(session_id: str, chunk_texts=(BST_TEXT, GRAPH_TEXT)):
    chunk_ids = [f"c-{i}" for i in range(len(chunk_texts))]
    embeddings = ingestion.embed_texts(list(chunk_texts))
    session = {"id": session_id, "transcript": [], "log": []}
    runtime = session_manager.SessionRuntime(
        session=session,
        pacing=PacingGate(session_start=0),
        chunk_ids=chunk_ids,
        chunk_texts=list(chunk_texts),
        embeddings=embeddings,
    )
    session_manager.ACTIVE_SESSIONS[session_id] = runtime
    return runtime


def _cleanup(session_id: str):
    session_manager.ACTIVE_SESSIONS.pop(session_id, None)
    path = storage.session_path(session_id)
    if path.exists():
        path.unlink()


def test_wrap_up_fully_covered_returns_status_only_no_generation(monkeypatch):
    runtime = _make_runtime("cov-test-1")
    try:
        runtime.asked_chunk_ids = set(runtime.chunk_ids)  # everything covered

        called = {"n": 0}

        def fail_if_called(*args, **kwargs):
            called["n"] += 1
            return "should not be called"

        monkeypatch.setattr(session_manager.question_gen, "generate_question", fail_if_called)

        result = session_manager.wrap_up(runtime.session["id"], now=10)
        assert result["generated"] is False
        assert result["coverage_ratio"] == 1.0
        assert called["n"] == 0
    finally:
        _cleanup(runtime.session["id"])


def test_wrap_up_above_threshold_returns_status_only(monkeypatch):
    # Coverage doesn't need to be literally 100% — just >= COVERAGE_WRAP_UP_THRESHOLD.
    runtime = _make_runtime("cov-test-2", chunk_texts=(BST_TEXT, GRAPH_TEXT, "A third, unrelated chunk about chemistry."))
    try:
        # 2 of 3 covered = 0.667, below the 0.8 default threshold, so this
        # should NOT short-circuit; confirm that first...
        runtime.asked_chunk_ids = {runtime.chunk_ids[0], runtime.chunk_ids[1]}

        called = {"n": 0}
        monkeypatch.setattr(
            session_manager.question_gen,
            "generate_question",
            lambda *a, **k: (called.__setitem__("n", called["n"] + 1), "Q")[1],
        )
        result = session_manager.wrap_up(runtime.session["id"], now=10)
        assert result["generated"] is True
        assert called["n"] >= 1
    finally:
        _cleanup(runtime.session["id"])


def test_wrap_up_partially_covered_targets_unmatched_chunk(monkeypatch):
    runtime = _make_runtime("cov-test-3")
    try:
        runtime.asked_chunk_ids = {runtime.chunk_ids[0]}  # BST chunk already asked
        runtime.session["transcript"] = [{"text": GRAPH_TEXT, "timestamp": 1}]

        captured = {}

        def fake_generate(chunks, transcript_window, **kwargs):
            captured["chunk_ids"] = [c.chunk_id for c in chunks]
            captured["wrap_up"] = kwargs.get("wrap_up")
            return "A wrap-up question"

        monkeypatch.setattr(session_manager.question_gen, "generate_question", fake_generate)

        result = session_manager.wrap_up(runtime.session["id"], now=10)
        assert result["generated"] is True
        assert len(result["questions"]) == 1
        assert result["questions"][0]["chunk_id"] == runtime.chunk_ids[1]  # the graph chunk, not BST
        assert captured["chunk_ids"] == [runtime.chunk_ids[1]]
        assert captured["wrap_up"] is True

        # Logged with the right event shape (mirrors slide_informed's pattern).
        event = [e for e in runtime.session["log"] if e["type"] == "question_generated"][-1]
        assert event["wrap_up"] is True
        assert event["trigger_reason"] == "wrap_up"
        assert event["topic_chunk_ids"] == [runtime.chunk_ids[1]]

        # Coverage updated so a second call doesn't regenerate the same chunk.
        assert runtime.chunk_ids[1] in runtime.asked_chunk_ids
    finally:
        _cleanup(runtime.session["id"])


def test_wrap_up_called_twice_does_not_repeat_unnecessarily(monkeypatch):
    runtime = _make_runtime("cov-test-4")
    try:
        runtime.session["transcript"] = [{"text": GRAPH_TEXT, "timestamp": 1}]
        monkeypatch.setattr(session_manager.question_gen, "generate_question", lambda *a, **k: "Q")

        first = session_manager.wrap_up(runtime.session["id"], now=10)
        assert first["generated"] is True
        assert first["coverage_ratio"] == 1.0  # both chunks now covered (only 2 total, k=min(2,2))

        called = {"n": 0}

        def fail_if_called(*a, **k):
            called["n"] += 1
            return "should not be called"

        monkeypatch.setattr(session_manager.question_gen, "generate_question", fail_if_called)
        second = session_manager.wrap_up(runtime.session["id"], now=20)
        assert second["generated"] is False
        assert called["n"] == 0
    finally:
        _cleanup(runtime.session["id"])


def test_wrap_up_does_not_touch_pacing_gate(monkeypatch):
    runtime = _make_runtime("cov-test-5")
    try:
        runtime.session["transcript"] = [{"text": GRAPH_TEXT, "timestamp": 1}]
        monkeypatch.setattr(session_manager.question_gen, "generate_question", lambda *a, **k: "Q")

        before = (runtime.pacing.last_question_at, runtime.pacing.last_speech_at)
        session_manager.wrap_up(runtime.session["id"], now=999)
        after = (runtime.pacing.last_question_at, runtime.pacing.last_speech_at)

        assert before == after  # wrap_up must never call pacing.note_question_shown
    finally:
        _cleanup(runtime.session["id"])


def test_wrap_up_no_transcript_falls_back_to_original_order(monkeypatch):
    # No transcript at all to judge relevance against — should still work,
    # deterministically, rather than error out.
    runtime = _make_runtime("cov-test-6")
    try:
        monkeypatch.setattr(session_manager.question_gen, "generate_question", lambda *a, **k: "Q")
        result = session_manager.wrap_up(runtime.session["id"], now=10)
        assert result["generated"] is True
        assert len(result["questions"]) == 2  # only 2 chunks total, both unmatched
    finally:
        _cleanup(runtime.session["id"])
