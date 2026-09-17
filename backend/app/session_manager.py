"""In-memory orchestration for active sessions.

Ties together: transcript buffer, pacing gate, unit chunk embeddings,
retrieval, and question generation. Persists to JSON via storage.py after
every mutating event so a crash doesn't lose the log.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from . import config, ingestion, question_gen, retrieval, session_log, storage
from .pacing import PacingGate


@dataclass
class SessionRuntime:
    session: Dict[str, Any]
    pacing: PacingGate
    chunk_ids: List[str]
    chunk_texts: List[str]
    embeddings: np.ndarray


ACTIVE_SESSIONS: Dict[str, SessionRuntime] = {}


class SessionNotFound(Exception):
    pass


class UnitNotFound(Exception):
    pass


def _load_unit_arrays(unit_id: str):
    if not storage.unit_exists(unit_id):
        raise UnitNotFound(unit_id)
    unit = storage.load_unit(unit_id)
    chunk_ids = [c["id"] for c in unit["chunks"]]
    chunk_texts = [c["text"] for c in unit["chunks"]]
    embeddings = (
        np.array([c["embedding"] for c in unit["chunks"]], dtype=np.float32)
        if unit["chunks"]
        else np.zeros((0, 0), dtype=np.float32)
    )
    return unit, chunk_ids, chunk_texts, embeddings


def start_session(unit_id: str) -> Dict[str, Any]:
    unit, chunk_ids, chunk_texts, embeddings = _load_unit_arrays(unit_id)
    session_id = uuid.uuid4().hex[:12]
    now = time.time()
    session = session_log.new_session_record(session_id, unit_id, unit["name"], now)
    storage.save_session(session)

    runtime = SessionRuntime(
        session=session,
        pacing=PacingGate(session_start=now),
        chunk_ids=chunk_ids,
        chunk_texts=chunk_texts,
        embeddings=embeddings,
    )
    ACTIVE_SESSIONS[session_id] = runtime
    return session


def _get_runtime(session_id: str) -> SessionRuntime:
    runtime = ACTIVE_SESSIONS.get(session_id)
    if runtime is None:
        raise SessionNotFound(session_id)
    return runtime


def add_transcript(session_id: str, text: str, timestamp: Optional[float] = None) -> None:
    runtime = _get_runtime(session_id)
    ts = timestamp if timestamp is not None else time.time()
    runtime.session["transcript"].append({"text": text, "timestamp": ts})
    runtime.pacing.note_speech(ts)
    storage.save_session(runtime.session)


def add_note(session_id: str, text: str, timestamp: Optional[float] = None) -> Dict[str, Any]:
    runtime = _get_runtime(session_id)
    ts = timestamp if timestamp is not None else time.time()
    event = session_log.log_event(runtime.session, "teacher_note", timestamp=ts, text=text)
    storage.save_session(runtime.session)
    return event


def _recent_transcript_window(runtime: SessionRuntime, now: float, window_seconds: int) -> str:
    cutoff = now - window_seconds
    recent = [t["text"] for t in runtime.session["transcript"] if t["timestamp"] >= cutoff]
    return " ".join(recent)


def _chunk_preview(text: str, max_words: int = 12) -> str:
    words = text.split()
    preview = " ".join(words[:max_words])
    return preview + ("..." if len(words) > max_words else "")


def match_topic(session_id: str, now: Optional[float] = None) -> List[retrieval.ScoredChunk]:
    """Run topic matching against the recent transcript window and log it."""
    runtime = _get_runtime(session_id)
    now = now if now is not None else time.time()
    window_text = _recent_transcript_window(runtime, now, config.MATCH_WINDOW_SECONDS)

    if not window_text.strip() or runtime.embeddings.shape[0] == 0:
        top_chunks: List[retrieval.ScoredChunk] = []
    else:
        query_vec = ingestion.embed_text(window_text)
        top_chunks = retrieval.top_k_chunks(
            query_vec, runtime.chunk_ids, runtime.chunk_texts, runtime.embeddings
        )

    session_log.log_event(
        runtime.session,
        "topic_match",
        window_text_preview=_chunk_preview(window_text, 20),
        top_chunks=[
            {"chunk_id": c.chunk_id, "score": c.score, "preview": _chunk_preview(c.text)}
            for c in top_chunks
        ],
    )
    storage.save_session(runtime.session)
    return top_chunks


def tick(session_id: str, now: Optional[float] = None, force: bool = False) -> Dict[str, Any]:
    """Called periodically by the frontend. Fires a question if the pacing
    gate allows it (or if force=True, for manual testing)."""
    runtime = _get_runtime(session_id)
    now = now if now is not None else time.time()

    decision = runtime.pacing.check(now)
    if not (decision.triggered or force):
        return {"triggered": False}

    reason = decision.reason if decision.triggered else "manual"
    top_chunks = match_topic(session_id, now)
    window_text = _recent_transcript_window(runtime, now, config.MATCH_WINDOW_SECONDS)

    question_text = question_gen.generate_question(top_chunks, window_text)

    event = session_log.log_event(
        runtime.session,
        "question_generated",
        question=question_text,
        trigger_reason=reason,
        shown=True,
        topic_chunk_ids=[c.chunk_id for c in top_chunks],
    )
    runtime.pacing.note_question_shown(now)
    storage.save_session(runtime.session)

    return {
        "triggered": True,
        "reason": reason,
        "question": question_text,
        "timestamp": event["timestamp"],
        "topic_chunks": [{"chunk_id": c.chunk_id, "preview": _chunk_preview(c.text)} for c in top_chunks],
        "ai_label": config.AI_LABEL,
    }


def end_session(session_id: str, now: Optional[float] = None) -> Dict[str, Any]:
    runtime = _get_runtime(session_id)
    now = now if now is not None else time.time()
    runtime.session["ended_at"] = now
    session_log.log_event(runtime.session, "session_end")
    storage.save_session(runtime.session)
    report = session_log.generate_report(runtime.session)
    del ACTIVE_SESSIONS[session_id]
    return report


def get_report(session_id: str) -> Dict[str, Any]:
    if session_id in ACTIVE_SESSIONS:
        session = ACTIVE_SESSIONS[session_id].session
    elif storage.session_exists(session_id):
        session = storage.load_session(session_id)
    else:
        raise SessionNotFound(session_id)
    return session_log.generate_report(session)
