"""FastAPI app: unit ingestion, session orchestration, and static frontend."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, config, ingestion, lti, session_manager, storage
from .auth import User, optional_user, require_teacher

app = FastAPI(title="Doubt-Clearing AI Co-host", version="0.2.0")
app.include_router(lti.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


# --- Schemas ---

class CreateUnitRequest(BaseModel):
    name: str
    text: str


class UnitSummary(BaseModel):
    id: str
    name: str
    num_chunks: int


class StartSessionRequest(BaseModel):
    unit_id: str
    # Planned class length; the AI controller uses it to judge "near the
    # end" for wrap-up. Defaults to CLASS_LENGTH_MINUTES.
    class_minutes: Optional[int] = Field(default=None, ge=10, le=300)


class PauseRequest(BaseModel):
    paused: bool


class TranscriptChunkRequest(BaseModel):
    text: str
    timestamp: Optional[float] = None


class NoteRequest(BaseModel):
    text: str


class TickRequest(BaseModel):
    force: bool = False


class FrameRequest(BaseModel):
    frame: str  # base64 JPEG, raw or as a data URL


# --- Access helpers ---

def _require_session_access(session_id: str, user: User) -> None:
    """404 (not 403) for someone else's session, so ids can't be probed."""
    try:
        session = session_manager.get_session_record(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    if not auth.can_see_session(user, session):
        raise HTTPException(404, "Session not found or already ended")


def _require_unit_access(unit_id: str, user: User) -> dict:
    if not storage.unit_exists(unit_id):
        raise HTTPException(404, "Unit not found")
    unit = storage.load_unit(unit_id)
    if not auth.can_see_course_item(user, unit.get("course_id")):
        raise HTTPException(404, "Unit not found")
    return unit


# --- Health and identity ---

@app.get("/health")
def health():
    return {"status": "ok", "ai_label": config.AI_LABEL, "controller_mode": config.CONTROLLER_MODE}


@app.get("/auth/me")
def me(user: Optional[User] = Depends(optional_user)):
    """Lets the frontend know whether sign-in is required and who is
    signed in. Never fails: an unauthenticated caller just gets
    authenticated=false."""
    return {
        "auth_required": config.AUTH_REQUIRED,
        "authenticated": user is not None,
        "name": user.name if user else None,
        "course_title": user.course_title if user else None,
        "is_staff": user.is_staff if user else False,
    }


# --- Units ---

@app.post("/units", response_model=UnitSummary)
def create_unit(req: CreateUnitRequest, user: User = Depends(require_teacher)):
    if not req.text.strip():
        raise HTTPException(400, "Unit text is empty")

    chunks = ingestion.chunk_text(req.text)
    if not chunks:
        raise HTTPException(400, "No chunks could be produced from this text")

    embeddings = ingestion.embed_texts(chunks)
    unit_id = uuid.uuid4().hex[:10]
    unit = {
        "id": unit_id,
        "name": req.name,
        "created_at": time.time(),
        "course_id": user.course_id,
        "created_by": user.sub if user.authenticated else None,
        "chunks": [
            {"id": f"{unit_id}-{i}", "text": chunk, "embedding": embeddings[i].tolist()}
            for i, chunk in enumerate(chunks)
        ],
    }
    storage.save_unit(unit)
    return UnitSummary(id=unit_id, name=req.name, num_chunks=len(chunks))


@app.get("/units", response_model=List[UnitSummary])
def list_units(user: User = Depends(require_teacher)):
    return [u for u in storage.list_units() if auth.can_see_course_item(user, u.get("course_id"))]


@app.get("/units/{unit_id}")
def get_unit(unit_id: str, user: User = Depends(require_teacher)):
    unit = _require_unit_access(unit_id, user)
    return {
        "id": unit["id"],
        "name": unit["name"],
        "chunks": [{"id": c["id"], "text": c["text"]} for c in unit["chunks"]],
    }


# --- Sessions ---

@app.post("/sessions")
def start_session(req: StartSessionRequest, user: User = Depends(require_teacher)):
    _require_unit_access(req.unit_id, user)
    try:
        session = session_manager.start_session(
            req.unit_id,
            owner_sub=user.sub if user.authenticated else None,
            course_id=user.course_id,
            class_minutes=req.class_minutes,
        )
    except session_manager.UnitNotFound:
        raise HTTPException(404, "Unit not found")
    return {
        "session_id": session["id"],
        "unit_id": session["unit_id"],
        "unit_name": session["unit_name"],
        "started_at": session["started_at"],
        "ai_label": session["ai_label"],
    }


@app.post("/sessions/{session_id}/transcript")
def post_transcript(session_id: str, req: TranscriptChunkRequest, user: User = Depends(require_teacher)):
    _require_session_access(session_id, user)
    if not req.text.strip():
        return {"ok": True}
    try:
        session_manager.add_transcript(session_id, req.text, req.timestamp)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return {"ok": True}


@app.post("/sessions/{session_id}/activity")
def post_participant_activity(session_id: str, user: User = Depends(require_teacher)):
    """Someone in the class (not the teacher) is speaking, as detected in
    the browser from the shared Meet tab's audio. No audio or transcript
    is sent: just the fact that someone spoke, used to hold questions
    back. Server time is used so client clock drift can't matter."""
    _require_session_access(session_id, user)
    try:
        session_manager.note_participant_activity(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return {"ok": True}


@app.post("/sessions/{session_id}/match")
def post_match(session_id: str, user: User = Depends(require_teacher)):
    _require_session_access(session_id, user)
    try:
        top_chunks = session_manager.match_topic(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return {"top_chunks": [{"chunk_id": c.chunk_id, "score": c.score, "text": c.text} for c in top_chunks]}


@app.post("/sessions/{session_id}/tick")
def post_tick(session_id: str, req: TickRequest = TickRequest(), user: User = Depends(require_teacher)):
    _require_session_access(session_id, user)
    try:
        result = session_manager.tick(session_id, force=req.force)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return result


@app.post("/sessions/{session_id}/frame")
def post_frame(session_id: str, req: FrameRequest, user: User = Depends(require_teacher)):
    """Optional: a captured slide frame, sent only while the teacher has
    chosen to share a window/tab/screen. Perception only — this can never
    trigger a question by itself, only sharpen the next pacing-gated
    tick()'s topic match. If nothing is ever posted here, the session
    behaves exactly as it did before this endpoint existed."""
    _require_session_access(session_id, user)
    if not req.frame.strip():
        raise HTTPException(400, "Frame is empty")
    try:
        return session_manager.process_frame(session_id, req.frame)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")


@app.post("/sessions/{session_id}/pause")
def post_pause(session_id: str, req: PauseRequest, user: User = Depends(require_teacher)):
    """The teacher's pause switch: while paused, the co-host never acts on
    its own. Manual 'Force question' and 'Wrap up unit' still work."""
    _require_session_access(session_id, user)
    try:
        return session_manager.set_paused(session_id, req.paused)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")


@app.post("/sessions/{session_id}/wrap-up")
def post_wrap_up(session_id: str, user: User = Depends(require_teacher)):
    """Deliberate end-of-unit coverage pass — teacher-triggered only, never
    the pacing gate, never NLP-detected from the transcript. Doesn't end
    the session; callable independently, same as /note."""
    _require_session_access(session_id, user)
    try:
        return session_manager.wrap_up(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")


@app.post("/sessions/{session_id}/note")
def post_note(session_id: str, req: NoteRequest, user: User = Depends(require_teacher)):
    _require_session_access(session_id, user)
    if not req.text.strip():
        raise HTTPException(400, "Note text is empty")
    try:
        event = session_manager.add_note(session_id, req.text)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return {"ok": True, "timestamp": event["timestamp"]}


@app.post("/sessions/{session_id}/end")
def post_end_session(session_id: str, user: User = Depends(require_teacher)):
    _require_session_access(session_id, user)
    try:
        report = session_manager.end_session(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return report


@app.get("/sessions/{session_id}/report")
def get_report(session_id: str, user: User = Depends(require_teacher)):
    _require_session_access(session_id, user)
    try:
        return session_manager.get_report(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found")


@app.get("/sessions/{session_id}/report.md", response_class=PlainTextResponse)
def get_report_markdown(session_id: str, user: User = Depends(require_teacher)):
    from .session_log import render_report_markdown

    _require_session_access(session_id, user)
    try:
        report = session_manager.get_report(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found")
    return render_report_markdown(report)


# --- Static frontend (served from the same origin to avoid CORS entirely) ---
#
# The React app is a client-side-routed SPA (react-router-dom: "/" is the
# landing page, "/app" is the tool). A plain StaticFiles mount at "/" only
# serves index.html for the exact root path, not for "/app" — that would
# 404 on a hard refresh or a direct/bookmarked visit, since there's no
# literal "app" file on disk for it to find. So instead: hashed JS/CSS
# assets are served directly from /assets, and everything else falls
# through to this catch-all, which always serves index.html and lets
# react-router-dom take over client-side routing in the browser. All the
# API routes above are matched first (FastAPI checks routes in registration
# order), so this never shadows them.

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        return FileResponse(FRONTEND_DIR / "index.html")
