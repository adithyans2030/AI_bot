"""In-memory orchestration for active sessions.

Ties together: transcript buffer, pacing gate, unit chunk embeddings,
retrieval, and question generation. Persists to JSON via storage.py after
every mutating event so a crash doesn't lose the log.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import numpy as np

from . import config, ingestion, question_gen, retrieval, session_log, slide_vision, storage
from .pacing import PacingGate


@dataclass
class SlideState:
    """In-memory only — never persisted. Holds at most the single most
    recent frame's thumbnail (for cheap perceptual diffing) and the single
    most recent high-confidence slide read. No frame history, no image
    storage beyond that one thumbnail."""

    thumbnail: Optional[np.ndarray] = None
    slide_title: Optional[str] = None
    key_text: Optional[str] = None
    confidence: str = "low"
    last_frame_at: float = 0.0


@dataclass
class SessionRuntime:
    session: Dict[str, Any]
    pacing: PacingGate
    chunk_ids: List[str]
    chunk_texts: List[str]
    embeddings: np.ndarray
    slide: SlideState = field(default_factory=SlideState)
    # Coverage tracking: chunk_ids that have been the basis of a fired
    # question this session (updated in tick() and wrap_up()). In-memory
    # only during the session, same as SlideState — the persisted-log
    # equivalent is derived on demand in session_log.generate_report() from
    # each question_generated event's topic_chunk_ids, so this doesn't need
    # its own persistence.
    asked_chunk_ids: Set[str] = field(default_factory=set)
    # FastAPI runs sync route handlers in a thread pool, so overlapping
    # requests for the SAME session are genuinely possible — and likely in
    # practice, since the frontend polls tick() every 5s while a real LLM
    # call routinely takes longer than that. Without this lock, multiple
    # concurrent tick() calls can all see "pacing gate says fire" before
    # any of them updates the gate, and all fire a question. Guards tick()
    # only (see there for why): the endpoint that's actually polled
    # automatically and repeatedly, not the click-triggered ones.
    lock: threading.Lock = field(default_factory=threading.Lock)


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


def start_session(unit_id: str, owner_sub: Optional[str] = None, course_id: Optional[str] = None) -> Dict[str, Any]:
    unit, chunk_ids, chunk_texts, embeddings = _load_unit_arrays(unit_id)
    session_id = uuid.uuid4().hex[:12]
    now = time.time()
    session = session_log.new_session_record(
        session_id, unit_id, unit["name"], now, total_chunks=len(chunk_ids)
    )
    # Moodle user id of the teacher who started it (None when auth is off),
    # so only that teacher can drive or read this session.
    session["owner_sub"] = owner_sub
    session["course_id"] = course_id
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


def get_session_record(session_id: str) -> Dict[str, Any]:
    """The session record, active or already ended (for access checks)."""
    runtime = ACTIVE_SESSIONS.get(session_id)
    if runtime is not None:
        return runtime.session
    if storage.session_exists(session_id):
        return storage.load_session(session_id)
    raise SessionNotFound(session_id)


def note_participant_activity(session_id: str, timestamp: Optional[float] = None) -> None:
    """Someone in the class (not the teacher) was heard in the shared Meet
    tab's audio. Feeds the pacing gate's human-priority hold only.

    Deliberately in memory only: never logged, persisted or reported. Who
    spoke, how often, or for how long is participation data, which this
    system never records (same guardrail as attendance)."""
    runtime = _get_runtime(session_id)
    runtime.pacing.note_participant_speech(timestamp if timestamp is not None else time.time())


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


def _asked_previews(runtime: SessionRuntime) -> List[str]:
    """Short previews of already-asked chunks, for the "don't repeat these"
    block in the question-generation prompt. Sorted for determinism (the
    underlying set has no stable order)."""
    id_to_text = dict(zip(runtime.chunk_ids, runtime.chunk_texts))
    return [
        _chunk_preview(id_to_text[chunk_id])
        for chunk_id in sorted(runtime.asked_chunk_ids)
        if chunk_id in id_to_text
    ]


# --- Slide capture (optional signal, alongside transcript matching) ---
#
# Perception only: process_frame() reads a frame and updates in-memory
# state. It never touches the pacing gate and never calls question_gen
# directly — a slide can never trigger a question by itself, only sharpen
# the topic match the next time the existing pacing-gated tick() fires.


def _slide_snapshot(runtime: SessionRuntime) -> Dict[str, Any]:
    return {
        "slide_title": runtime.slide.slide_title,
        "key_text": runtime.slide.key_text,
        "confidence": runtime.slide.confidence,
    }


def process_frame(session_id: str, frame: str, now: Optional[float] = None) -> Dict[str, Any]:
    """Called when the frontend sends a captured slide frame."""
    runtime = _get_runtime(session_id)
    now = now if now is not None else time.time()

    new_thumb = slide_vision.frame_thumbnail(frame)
    previous_thumb = runtime.slide.thumbnail
    diff = slide_vision.thumbnail_diff(new_thumb, previous_thumb)

    # Every frame that arrives, whether or not it triggers a fresh vision
    # call, proves sharing is still active — this is what keeps a static
    # slide from going "stale" just because it hasn't visually changed.
    runtime.slide.last_frame_at = now
    if new_thumb is not None:
        runtime.slide.thumbnail = new_thumb

    if previous_thumb is not None and diff < config.SLIDE_FRAME_DIFF_THRESHOLD:
        # Slide hasn't visibly changed since the last processed frame —
        # skip the (comparatively expensive) vision call entirely.
        return {"processed": False, "slide": _slide_snapshot(runtime)}

    read = slide_vision.read_slide(frame)
    if read["confidence"] == "high":
        runtime.slide.slide_title = read["slide_title"]
        runtime.slide.key_text = read["key_text"]
        runtime.slide.confidence = "high"
    # else: low-confidence read, discarded per spec — deliberately NOT
    # cleared here either. A single bad frame (transition, glare) shouldn't
    # wipe out a still-relevant title; staleness (see _current_slide_signal)
    # is what eventually retires an old read if sharing actually stopped.

    return {"processed": True, "slide": _slide_snapshot(runtime)}


def _current_slide_signal(runtime: SessionRuntime, now: float) -> Optional[Dict[str, Optional[str]]]:
    """The slide's title/text if a fresh, high-confidence read exists,
    else None — meaning "behave exactly as if slide capture were off"."""
    slide = runtime.slide
    if slide.confidence != "high" or not slide.slide_title:
        return None
    if now - slide.last_frame_at > config.SLIDE_STALENESS_SECONDS:
        return None
    return {"slide_title": slide.slide_title, "key_text": slide.key_text}


def match_topic(session_id: str, now: Optional[float] = None) -> List[retrieval.ScoredChunk]:
    """Run topic matching against the recent transcript window, and — when
    a fresh slide read is available — also against the slide's title/text,
    then merge. Run and log exactly as before when no slide signal exists
    (the default: nothing changes if this feature is never used)."""
    runtime = _get_runtime(session_id)
    now = now if now is not None else time.time()
    window_text = _recent_transcript_window(runtime, now, config.MATCH_WINDOW_SECONDS)
    slide_signal = _current_slide_signal(runtime, now)

    top_chunks: List[retrieval.ScoredChunk] = []
    if runtime.embeddings.shape[0] > 0:
        # Merge strategy: take the MAX score per chunk across the
        # transcript-window query and the slide-text query, not an
        # average. A slide title is a direct, unambiguous topic signal;
        # averaging it against a possibly-weak or off-topic transcript
        # score for that same chunk would water down a strong match
        # instead of trusting it. Whichever signal is more confident about
        # a given chunk wins for that chunk.
        best_by_id: Dict[str, retrieval.ScoredChunk] = {}
        all_ids_k = len(runtime.chunk_ids)

        # Both queries below get the coverage penalty (soft, see
        # retrieval.top_k_chunks) — either one could otherwise re-surface
        # an already-covered chunk.
        if window_text.strip():
            query_vec = ingestion.embed_text(window_text)
            for c in retrieval.top_k_chunks(
                query_vec,
                runtime.chunk_ids,
                runtime.chunk_texts,
                runtime.embeddings,
                k=all_ids_k,
                asked_chunk_ids=runtime.asked_chunk_ids,
            ):
                best_by_id[c.chunk_id] = c

        if slide_signal:
            slide_query = f"{slide_signal['slide_title']}. {slide_signal['key_text'] or ''}".strip()
            slide_vec = ingestion.embed_text(slide_query)
            for c in retrieval.top_k_chunks(
                slide_vec,
                runtime.chunk_ids,
                runtime.chunk_texts,
                runtime.embeddings,
                k=all_ids_k,
                asked_chunk_ids=runtime.asked_chunk_ids,
            ):
                existing = best_by_id.get(c.chunk_id)
                if existing is None or c.score > existing.score:
                    best_by_id[c.chunk_id] = c

        top_chunks = sorted(best_by_id.values(), key=lambda c: -c.score)[: config.RETRIEVAL_TOP_K]

    session_log.log_event(
        runtime.session,
        "topic_match",
        window_text_preview=_chunk_preview(window_text, 20),
        slide_informed=slide_signal is not None,
        top_chunks=[
            {"chunk_id": c.chunk_id, "score": c.score, "preview": _chunk_preview(c.text)}
            for c in top_chunks
        ],
    )
    storage.save_session(runtime.session)
    return top_chunks


def tick(session_id: str, now: Optional[float] = None, force: bool = False) -> Dict[str, Any]:
    """Called periodically by the frontend. Fires a question if the pacing
    gate allows it (or if force=True, for manual testing).

    Two guardrails live here, both hardening against real failure modes
    seen in practice, not hypothetical ones:

    1. Concurrency: a real local LLM call routinely takes longer than the
       frontend's poll interval, so overlapping tick() calls for the same
       session are the normal case, not an edge case. Uses a non-blocking
       per-session lock — if a previous tick() is still generating, this
       one just no-ops instead of queueing up and firing a second,
       redundant question once unblocked.
    2. No fabricating from nothing: if there's truly no transcript, no
       slide signal, and nothing matched, there's nothing to ground a
       question in — generating one anyway means the model invents an
       unrelated question for a random subject rather than admitting it
       has nothing to ask about. Skip firing instead.
    """
    runtime = _get_runtime(session_id)
    now = now if now is not None else time.time()

    decision = runtime.pacing.check(now)
    if not (decision.triggered or force):
        return {"triggered": False}

    if not runtime.lock.acquire(blocking=False):
        return {"triggered": False}

    try:
        # Re-check now that the lock is held — pacing state may have
        # changed while waiting (e.g. another tick just fired and updated it).
        decision = runtime.pacing.check(now)
        if not (decision.triggered or force):
            return {"triggered": False}

        reason = decision.reason if decision.triggered else "manual"
        top_chunks = match_topic(session_id, now)
        window_text = _recent_transcript_window(runtime, now, config.MATCH_WINDOW_SECONDS)
        slide_signal = _current_slide_signal(runtime, now)
        slide_text = slide_signal["key_text"] or slide_signal["slide_title"] if slide_signal else None

        if not top_chunks and not window_text.strip() and not slide_text:
            return {"triggered": False, "reason": "no_content"}

        # Previews of chunks asked about in EARLIER ticks this session —
        # computed before this tick's own top_chunks are added below.
        asked_previews = _asked_previews(runtime)

        participant_marker = runtime.pacing.last_participant_at
        question_text = question_gen.generate_question(
            top_chunks, window_text, slide_text=slide_text, previously_asked_previews=asked_previews
        )

        # Human priority, part 2: generation takes seconds. If a student
        # started speaking meanwhile, drop the question rather than talk
        # over them. The gate isn't advanced, so it can fire again once the
        # class goes quiet. (A manual force=True test question is kept.)
        if not force and runtime.pacing.last_participant_at != participant_marker:
            session_log.log_event(
                runtime.session,
                "question_suppressed",
                reason="participant_spoke",
                question=question_text,
                topic_chunk_ids=[c.chunk_id for c in top_chunks],
            )
            storage.save_session(runtime.session)
            return {"triggered": False, "reason": "participant_spoke"}

        event = session_log.log_event(
            runtime.session,
            "question_generated",
            question=question_text,
            trigger_reason=reason,
            shown=True,
            topic_chunk_ids=[c.chunk_id for c in top_chunks],
            slide_informed=slide_signal is not None,
        )
        runtime.pacing.note_question_shown(now)
        # Every fired question updates coverage — pacing-triggered or
        # force=True manual triggers alike, since both go through this path.
        runtime.asked_chunk_ids.update(c.chunk_id for c in top_chunks)
        storage.save_session(runtime.session)

        return {
            "triggered": True,
            "reason": reason,
            "question": question_text,
            "timestamp": event["timestamp"],
            "topic_chunks": [{"chunk_id": c.chunk_id, "preview": _chunk_preview(c.text)} for c in top_chunks],
            "ai_label": config.AI_LABEL,
            "slide_informed": slide_signal is not None,
        }
    finally:
        runtime.lock.release()


def wrap_up(session_id: str, now: Optional[float] = None) -> Dict[str, Any]:
    """Deliberate end-of-session coverage pass. Triggered explicitly by the
    teacher (POST /sessions/{id}/wrap-up) — never by the pacing gate, and
    never automatically from transcript content (no "sounds like class is
    ending" NLP detection by design). Does NOT end the session or touch
    the pacing gate; callable independently while the session is still
    active, the same way add_note() is.

    If the unit's already sufficiently covered (>= config.COVERAGE_WRAP_UP_THRESHOLD
    of chunks touched, or nothing left uncovered), returns a status-only
    result and does NOT call question_gen — no manufactured question just
    to have something to show. Otherwise generates 1-2 questions grounded
    in chunks that were never the basis of a fired question this session,
    picked by relevance to the *full* session transcript so the pick is
    "uncovered AND still relevant to what was actually discussed," not
    arbitrary.
    """
    runtime = _get_runtime(session_id)
    now = now if now is not None else time.time()

    total = len(runtime.chunk_ids)
    coverage_ratio = (len(runtime.asked_chunk_ids) / total) if total > 0 else 1.0
    unmatched_indices = [i for i, cid in enumerate(runtime.chunk_ids) if cid not in runtime.asked_chunk_ids]

    if not unmatched_indices or coverage_ratio >= config.COVERAGE_WRAP_UP_THRESHOLD:
        return {
            "generated": False,
            "coverage_ratio": coverage_ratio,
            "message": "Session covered the unit's main content.",
        }

    unmatched_ids = [runtime.chunk_ids[i] for i in unmatched_indices]
    unmatched_texts = [runtime.chunk_texts[i] for i in unmatched_indices]
    unmatched_embeddings = runtime.embeddings[unmatched_indices]

    full_transcript = " ".join(t["text"] for t in runtime.session["transcript"])
    if full_transcript.strip():
        query_vec = ingestion.embed_text(full_transcript)
    else:
        # Nothing to judge relevance against — fall back to a neutral zero
        # vector, which ties every chunk's score and just takes the first
        # couple of unmatched chunks in original order.
        query_vec = np.zeros(unmatched_embeddings.shape[1], dtype=np.float32)

    picked = retrieval.top_k_chunks(
        query_vec, unmatched_ids, unmatched_texts, unmatched_embeddings, k=min(2, len(unmatched_ids))
    )

    questions: List[Dict[str, Any]] = []
    for chunk in picked:
        question_text = question_gen.generate_question(
            [chunk],
            full_transcript,
            previously_asked_previews=_asked_previews(runtime),
            wrap_up=True,
        )
        event = session_log.log_event(
            runtime.session,
            "question_generated",
            question=question_text,
            trigger_reason="wrap_up",
            shown=True,
            topic_chunk_ids=[chunk.chunk_id],
            slide_informed=False,
            wrap_up=True,
        )
        runtime.asked_chunk_ids.add(chunk.chunk_id)
        questions.append({"question": question_text, "timestamp": event["timestamp"], "chunk_id": chunk.chunk_id})

    storage.save_session(runtime.session)

    return {
        "generated": True,
        "coverage_ratio": (len(runtime.asked_chunk_ids) / total) if total > 0 else 1.0,
        "questions": questions,
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
