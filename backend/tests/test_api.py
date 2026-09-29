"""Integration tests for the FastAPI routes, driven through session_manager.

Deliberately never trigger question generation (no force=True tick on an
otherwise-idle session) — that would require a running local LLM and make
this suite slow/flaky/network-dependent. The pacing-gate and LLM-call logic
themselves are covered separately: pacing in test_pacing.py, and
question_gen is exercised manually/live (see README), not in this suite.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app import storage

client = TestClient(app)

SAMPLE_UNIT_TEXT = " ".join(["binary search trees are a data structure"] * 40)


def _make_unit(name="Test Unit"):
    resp = client.post("/units", json={"name": name, "text": SAMPLE_UNIT_TEXT})
    assert resp.status_code == 200
    return resp.json()


def _cleanup_unit(unit_id):
    path = storage.unit_path(unit_id)
    if path.exists():
        path.unlink()


def _cleanup_session(session_id):
    path = storage.session_path(session_id)
    if path.exists():
        path.unlink()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_list_unit():
    unit = _make_unit("BST Unit")
    try:
        assert unit["name"] == "BST Unit"
        assert unit["num_chunks"] >= 1

        listed = client.get("/units").json()
        assert any(u["id"] == unit["id"] for u in listed)

        detail = client.get(f"/units/{unit['id']}").json()
        assert detail["name"] == "BST Unit"
        assert len(detail["chunks"]) == unit["num_chunks"]
    finally:
        _cleanup_unit(unit["id"])


def test_create_unit_rejects_empty_text():
    resp = client.post("/units", json={"name": "Empty", "text": "   "})
    assert resp.status_code == 400


def test_get_unknown_unit_404s():
    resp = client.get("/units/does-not-exist")
    assert resp.status_code == 404


def test_start_session_unknown_unit_404s():
    resp = client.post("/sessions", json={"unit_id": "does-not-exist"})
    assert resp.status_code == 404


def test_full_session_lifecycle_without_triggering_llm():
    unit = _make_unit("Lifecycle Unit")
    session = None
    try:
        session = client.post("/sessions", json={"unit_id": unit["id"]}).json()
        assert session["unit_id"] == unit["id"]
        assert "not a student" in session["ai_label"]
        session_id = session["session_id"]

        # Transcript logging.
        resp = client.post(f"/sessions/{session_id}/transcript", json={"text": "hello class"})
        assert resp.status_code == 200

        # Topic match (embeds locally, no LLM call).
        match = client.post(f"/sessions/{session_id}/match").json()
        assert "top_chunks" in match

        # Tick with force=False, immediately after start: pacing gate must
        # NOT trigger yet (no silence elapsed, no interval elapsed) — so
        # this never reaches question_gen / the LLM.
        tick = client.post(f"/sessions/{session_id}/tick", json={"force": False}).json()
        assert tick == {"triggered": False}

        # Teacher note.
        note = client.post(f"/sessions/{session_id}/note", json={"text": "answered live"})
        assert note.status_code == 200

        # End session, check the report is honest: no attendance data,
        # zero questions (since we never triggered one above).
        report = client.post(f"/sessions/{session_id}/end").json()
        assert report["unit_id"] == unit["id"]
        assert report["questions"] == []
        assert len(report["teacher_notes"]) == 1
        assert "attendance" not in str(report).lower()

        # Session is over — further ticks against it should 404.
        resp = client.post(f"/sessions/{session_id}/tick", json={"force": False})
        assert resp.status_code == 404
    finally:
        _cleanup_unit(unit["id"])
        if session:
            _cleanup_session(session["session_id"])


def test_spa_fallback_serves_index_for_app_route():
    # The React app is client-side routed; a direct hit to /app must not
    # 404 (regression test for the StaticFiles-mount-shadows-catch-all bug).
    resp = client.get("/app")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_spa_fallback_does_not_shadow_api_routes():
    # The catch-all must never intercept a real, registered API route.
    resp = client.get("/units")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
