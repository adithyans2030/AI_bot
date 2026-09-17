"""FastAPI app: unit ingestion, session orchestration, and static frontend."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, ingestion, session_manager, storage

app = FastAPI(title="Doubt-Clearing AI Co-host", version="0.1.0")

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


class TranscriptChunkRequest(BaseModel):
    text: str
    timestamp: Optional[float] = None


class NoteRequest(BaseModel):
    text: str


class TickRequest(BaseModel):
    force: bool = False


# --- Health ---

@app.get("/health")
def health():
    return {"status": "ok", "ai_label": config.AI_LABEL}


# --- Units ---

@app.post("/units", response_model=UnitSummary)
def create_unit(req: CreateUnitRequest):
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
        "chunks": [
            {"id": f"{unit_id}-{i}", "text": chunk, "embedding": embeddings[i].tolist()}
            for i, chunk in enumerate(chunks)
        ],
    }
    storage.save_unit(unit)
    return UnitSummary(id=unit_id, name=req.name, num_chunks=len(chunks))


@app.get("/units", response_model=List[UnitSummary])
def list_units():
    return storage.list_units()


@app.get("/units/{unit_id}")
def get_unit(unit_id: str):
    if not storage.unit_exists(unit_id):
        raise HTTPException(404, "Unit not found")
    unit = storage.load_unit(unit_id)
    return {
        "id": unit["id"],
        "name": unit["name"],
        "chunks": [{"id": c["id"], "text": c["text"]} for c in unit["chunks"]],
    }


# --- Sessions ---

@app.post("/sessions")
def start_session(req: StartSessionRequest):
    try:
        session = session_manager.start_session(req.unit_id)
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
def post_transcript(session_id: str, req: TranscriptChunkRequest):
    if not req.text.strip():
        return {"ok": True}
    try:
        session_manager.add_transcript(session_id, req.text, req.timestamp)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return {"ok": True}


@app.post("/sessions/{session_id}/match")
def post_match(session_id: str):
    try:
        top_chunks = session_manager.match_topic(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return {"top_chunks": [{"chunk_id": c.chunk_id, "score": c.score, "text": c.text} for c in top_chunks]}


@app.post("/sessions/{session_id}/tick")
def post_tick(session_id: str, req: TickRequest = TickRequest()):
    try:
        result = session_manager.tick(session_id, force=req.force)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return result


@app.post("/sessions/{session_id}/note")
def post_note(session_id: str, req: NoteRequest):
    if not req.text.strip():
        raise HTTPException(400, "Note text is empty")
    try:
        event = session_manager.add_note(session_id, req.text)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return {"ok": True, "timestamp": event["timestamp"]}


@app.post("/sessions/{session_id}/end")
def post_end_session(session_id: str):
    try:
        report = session_manager.end_session(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found or already ended")
    return report


@app.get("/sessions/{session_id}/report")
def get_report(session_id: str):
    try:
        return session_manager.get_report(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found")


@app.get("/sessions/{session_id}/report.md", response_class=PlainTextResponse)
def get_report_markdown(session_id: str):
    from .session_log import render_report_markdown

    try:
        report = session_manager.get_report(session_id)
    except session_manager.SessionNotFound:
        raise HTTPException(404, "Session not found")
    return render_report_markdown(report)


# --- Static frontend (served from the same origin to avoid CORS entirely) ---

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
