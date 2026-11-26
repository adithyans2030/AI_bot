"""Regression tests for two failure modes seen in a real live run:

1. tick() fired a question with a fully empty transcript and no matched
   chunks — the model hallucinated an unrelated question for a random
   subject instead of having nothing to say. tick() must now skip firing
   when there's truly no content to ground a question in.
2. Multiple overlapping tick() calls for the same session (the frontend
   polls faster than a real LLM call resolves) all saw the pacing gate as
   "triggered" before any of them updated it, and all fired — 4 questions
   within ~2 seconds, all ungrounded. A non-blocking per-session lock must
   prevent this: a tick() call that finds the lock already held must no-op
   immediately, not queue up and fire once unblocked.
"""
from __future__ import annotations

from app import ingestion, session_manager, storage
from app.pacing import PacingGate

BST_TEXT = "Binary search trees support fast search by comparing keys and descending left or right at each node."


def _make_runtime(session_id: str):
    chunk_ids = ["c-0"]
    chunk_texts = [BST_TEXT]
    embeddings = ingestion.embed_texts(chunk_texts)
    session = {"id": session_id, "transcript": [], "log": []}
    runtime = session_manager.SessionRuntime(
        session=session,
        pacing=PacingGate(session_start=0),
        chunk_ids=chunk_ids,
        chunk_texts=chunk_texts,
        embeddings=embeddings,
    )
    session_manager.ACTIVE_SESSIONS[session_id] = runtime
    return runtime


def _cleanup(session_id: str):
    session_manager.ACTIVE_SESSIONS.pop(session_id, None)
    path = storage.session_path(session_id)
    if path.exists():
        path.unlink()


def test_tick_does_not_fabricate_a_question_with_no_content(monkeypatch):
    runtime = _make_runtime("guard-test-1")
    try:
        # No transcript at all -- exactly the real failure case: empty
        # session["transcript"], no slide, nothing for match_topic to find.
        called = {"n": 0}
        monkeypatch.setattr(
            session_manager.question_gen,
            "generate_question",
            lambda *a, **k: (called.__setitem__("n", called["n"] + 1), "should not happen")[1],
        )

        # Past PACING_MAX_INTERVAL_SECONDS (240 default), so the pacing gate
        # itself says "fire" -- the content guardrail is what must stop it.
        result = session_manager.tick(runtime.session["id"], now=300, force=False)

        assert result["triggered"] is False
        assert called["n"] == 0  # generate_question must never have been called
        # No fabricated question_generated event should be in the log.
        assert not [e for e in runtime.session["log"] if e["type"] == "question_generated"]
    finally:
        _cleanup(runtime.session["id"])


def test_tick_fires_normally_once_real_content_exists(monkeypatch):
    # Sanity check the guardrail isn't over-broad: real transcript content
    # must still produce a real question.
    runtime = _make_runtime("guard-test-2")
    try:
        runtime.session["transcript"] = [{"text": BST_TEXT, "timestamp": 290}]
        monkeypatch.setattr(session_manager.question_gen, "generate_question", lambda *a, **k: "A real question")

        result = session_manager.tick(runtime.session["id"], now=300, force=False)
        assert result["triggered"] is True
        assert result["question"] == "A real question"
    finally:
        _cleanup(runtime.session["id"])


def test_tick_noops_when_lock_already_held(monkeypatch):
    runtime = _make_runtime("guard-test-3")
    try:
        runtime.session["transcript"] = [{"text": BST_TEXT, "timestamp": 290}]
        called = {"n": 0}
        monkeypatch.setattr(
            session_manager.question_gen,
            "generate_question",
            lambda *a, **k: (called.__setitem__("n", called["n"] + 1), "Q")[1],
        )

        # Simulate a tick() call that's already "in flight" by holding the
        # lock, exactly like a slow LLM call would while it's running.
        runtime.lock.acquire()
        try:
            result = session_manager.tick(runtime.session["id"], now=300, force=True)
            assert result == {"triggered": False}
            assert called["n"] == 0
        finally:
            runtime.lock.release()

        # Once released, a normal tick() proceeds as usual.
        result2 = session_manager.tick(runtime.session["id"], now=300, force=True)
        assert result2["triggered"] is True
        assert called["n"] == 1
    finally:
        _cleanup(runtime.session["id"])


def test_concurrent_ticks_fire_at_most_once(monkeypatch):
    """Directly reproduces the real bug: several overlapping tick() calls
    for the same session, all past the pacing threshold. Without the lock,
    all of them would fire; with it, only one should."""
    import threading
    import time as time_module

    runtime = _make_runtime("guard-test-4")
    try:
        runtime.session["transcript"] = [{"text": BST_TEXT, "timestamp": 290}]

        def slow_generate(*a, **k):
            time_module.sleep(0.2)  # stand-in for real LLM latency
            return "Q"

        monkeypatch.setattr(session_manager.question_gen, "generate_question", slow_generate)

        results = []
        # All five calls start at the same instant, so they genuinely
        # overlap even on a busy machine. (Without this, a thread scheduled
        # after the first tick has finished would legitimately fire again,
        # making the test flaky under load.)
        start_together = threading.Barrier(5)

        def call_tick():
            start_together.wait()
            results.append(session_manager.tick(runtime.session["id"], now=300, force=True))

        threads = [threading.Thread(target=call_tick) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        triggered_count = sum(1 for r in results if r["triggered"])
        assert triggered_count == 1, f"expected exactly 1 fire, got {triggered_count}: {results}"

        questions_logged = [e for e in runtime.session["log"] if e["type"] == "question_generated"]
        assert len(questions_logged) == 1
    finally:
        _cleanup(runtime.session["id"])
