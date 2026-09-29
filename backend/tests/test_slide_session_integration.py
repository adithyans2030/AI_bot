"""Integration tests for the slide-vision signal merging into topic
matching and question generation.

Uses a monkeypatched slide_vision.read_slide() so these don't require a
real local vision model to be pulled — what's under test here is the
merge/staleness/discard logic in session_manager.py, not the vision model
call itself (that needs a live Ollama + a pulled vision model; see README
for the manual live test). Uses *real* embeddings (ingestion.embed_texts),
not mocked, so the retrieval-merge assertions reflect genuine behavior.
"""
from __future__ import annotations

import base64
import io

from PIL import Image

from app import ingestion, session_manager, slide_vision, storage
from app.pacing import PacingGate

BST_TEXT = "Binary search trees support fast search by comparing keys and descending left or right at each node."
BIO_TEXT = "Photosynthesis converts sunlight, water, and carbon dioxide into glucose and oxygen inside chloroplasts."


def _make_runtime(session_id: str) -> session_manager.SessionRuntime:
    chunk_ids = ["c-bst", "c-bio"]
    chunk_texts = [BST_TEXT, BIO_TEXT]
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


def _tiny_jpeg_frame(color=(50, 50, 50)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=color).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_slide_signal_sharpens_match_when_transcript_is_uninformative(monkeypatch):
    runtime = _make_runtime("slide-test-1")
    try:
        runtime.session["transcript"] = []  # nothing to go on from speech alone

        monkeypatch.setattr(
            slide_vision,
            "read_slide",
            lambda frame: {
                "slide_title": "Binary Search Trees",
                "key_text": "Deletion and search",
                "confidence": "high",
            },
        )

        result = session_manager.process_frame(runtime.session["id"], _tiny_jpeg_frame(), now=10)
        assert result["processed"] is True
        assert result["slide"]["confidence"] == "high"

        top_chunks = session_manager.match_topic(runtime.session["id"], now=11)
        assert top_chunks
        assert top_chunks[0].chunk_id == "c-bst"

        last_event = runtime.session["log"][-1]
        assert last_event["type"] == "topic_match"
        assert last_event["slide_informed"] is True
    finally:
        _cleanup(runtime.session["id"])


def test_no_frame_ever_sent_behaves_exactly_as_before():
    # Baseline regression: if slide capture is never used, matching stays
    # purely transcript-based, exactly as it worked before this feature.
    runtime = _make_runtime("slide-test-2")
    try:
        runtime.session["transcript"] = [{"text": BIO_TEXT, "timestamp": 5}]
        top_chunks = session_manager.match_topic(runtime.session["id"], now=6)
        assert top_chunks
        assert top_chunks[0].chunk_id == "c-bio"
        last_event = runtime.session["log"][-1]
        assert last_event["slide_informed"] is False
    finally:
        _cleanup(runtime.session["id"])


def test_low_confidence_read_is_discarded_not_used(monkeypatch):
    runtime = _make_runtime("slide-test-3")
    try:
        monkeypatch.setattr(
            slide_vision,
            "read_slide",
            lambda frame: dict(slide_vision._LOW_CONFIDENCE),
        )
        result = session_manager.process_frame(runtime.session["id"], _tiny_jpeg_frame(), now=10)
        assert result["slide"]["confidence"] == "low"

        # Only a low-confidence read and no transcript: matching should
        # find nothing, not a guessed match built on a discarded read.
        top_chunks = session_manager.match_topic(runtime.session["id"], now=11)
        assert top_chunks == []
    finally:
        _cleanup(runtime.session["id"])


def test_unchanged_frame_skips_the_vision_call(monkeypatch):
    runtime = _make_runtime("slide-test-4")
    try:
        call_count = {"n": 0}

        def fake_read_slide(frame):
            call_count["n"] += 1
            return {"slide_title": "Binary Search Trees", "key_text": "Search", "confidence": "high"}

        monkeypatch.setattr(slide_vision, "read_slide", fake_read_slide)

        frame = _tiny_jpeg_frame()
        session_manager.process_frame(runtime.session["id"], frame, now=10)
        session_manager.process_frame(runtime.session["id"], frame, now=20)  # visually identical

        assert call_count["n"] == 1
    finally:
        _cleanup(runtime.session["id"])


def test_changed_frame_does_not_skip_the_vision_call(monkeypatch):
    runtime = _make_runtime("slide-test-5")
    try:
        call_count = {"n": 0}

        def fake_read_slide(frame):
            call_count["n"] += 1
            return {"slide_title": "Binary Search Trees", "key_text": "Search", "confidence": "high"}

        monkeypatch.setattr(slide_vision, "read_slide", fake_read_slide)

        session_manager.process_frame(runtime.session["id"], _tiny_jpeg_frame((0, 0, 0)), now=10)
        session_manager.process_frame(runtime.session["id"], _tiny_jpeg_frame((255, 255, 255)), now=20)

        assert call_count["n"] == 2
    finally:
        _cleanup(runtime.session["id"])


def test_stale_slide_read_falls_back_to_transcript_only(monkeypatch):
    runtime = _make_runtime("slide-test-6")
    try:
        monkeypatch.setattr(
            slide_vision,
            "read_slide",
            lambda frame: {"slide_title": "Binary Search Trees", "key_text": "Search", "confidence": "high"},
        )
        session_manager.process_frame(runtime.session["id"], _tiny_jpeg_frame(), now=0)

        runtime.session["transcript"] = [{"text": BIO_TEXT, "timestamp": 100}]
        # Well past SLIDE_STALENESS_SECONDS (30s default) since that frame.
        top_chunks = session_manager.match_topic(runtime.session["id"], now=100)
        assert top_chunks
        assert top_chunks[0].chunk_id == "c-bio"  # transcript-only result; slide ignored
        last_event = runtime.session["log"][-1]
        assert last_event["slide_informed"] is False
    finally:
        _cleanup(runtime.session["id"])


def test_question_generation_receives_slide_signal_and_logs_it(monkeypatch):
    runtime = _make_runtime("slide-test-7")
    try:
        monkeypatch.setattr(
            slide_vision,
            "read_slide",
            lambda frame: {
                "slide_title": "Binary Search Trees",
                "key_text": "Deletion with two children",
                "confidence": "high",
            },
        )
        session_manager.process_frame(runtime.session["id"], _tiny_jpeg_frame(), now=0)

        captured = {}

        def fake_generate_question(chunks, transcript_window, slide_text=None):
            captured["slide_text"] = slide_text
            return "Fake question"

        monkeypatch.setattr(session_manager.question_gen, "generate_question", fake_generate_question)

        result = session_manager.tick(runtime.session["id"], now=1, force=True)
        assert result["slide_informed"] is True
        assert captured["slide_text"] == "Deletion with two children"

        questions = [e for e in runtime.session["log"] if e["type"] == "question_generated"]
        assert questions[-1]["slide_informed"] is True
    finally:
        _cleanup(runtime.session["id"])
