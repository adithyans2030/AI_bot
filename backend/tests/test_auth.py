"""API access control once AUTH_REQUIRED is on (production setting).

Embeddings are faked so these run fast; this is about who can reach what,
not retrieval quality.
"""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import auth, config, ingestion, session_manager, storage
from app.main import app

client = TestClient(app)
UNIT_TEXT = " ".join(["binary search trees keep keys ordered"] * 40)


@pytest.fixture(autouse=True)
def auth_on(monkeypatch):
    monkeypatch.setattr(config, "AUTH_REQUIRED", True)
    monkeypatch.setattr(config, "APP_SECRET", "test-secret-" + "y" * 32)
    monkeypatch.setattr(
        ingestion, "embed_texts", lambda texts: np.ones((len(texts), 8), dtype=np.float32)
    )
    monkeypatch.setattr(ingestion, "embed_text", lambda text: np.ones(8, dtype=np.float32))
    created = {"units": [], "sessions": []}
    yield created
    for unit_id in created["units"]:
        path = storage.unit_path(unit_id)
        if path.exists():
            path.unlink()
    for session_id in created["sessions"]:
        session_manager.ACTIVE_SESSIONS.pop(session_id, None)
        path = storage.session_path(session_id)
        if path.exists():
            path.unlink()


def _headers(sub="t1", course="course-A", staff=True):
    user = auth.User(sub=sub, name="T", is_staff=staff, course_id=course, course_title="Course")
    return {"Authorization": f"Bearer {auth.issue_app_token(user)}"}


def _make_unit(created, headers):
    resp = client.post("/units", json={"name": "BST", "text": UNIT_TEXT}, headers=headers)
    assert resp.status_code == 200, resp.text
    created["units"].append(resp.json()["id"])
    return resp.json()["id"]


def _start(created, unit_id, headers):
    resp = client.post("/sessions", json={"unit_id": unit_id}, headers=headers)
    assert resp.status_code == 200, resp.text
    created["sessions"].append(resp.json()["session_id"])
    return resp.json()["session_id"]


def test_health_and_me_stay_public():
    assert client.get("/health").status_code == 200
    me = client.get("/auth/me").json()
    assert me == {
        "auth_required": True,
        "authenticated": False,
        "name": None,
        "course_title": None,
        "is_staff": False,
    }


def test_me_reports_signed_in_teacher():
    me = client.get("/auth/me", headers=_headers()).json()
    assert me["authenticated"] is True and me["is_staff"] is True
    assert me["course_title"] == "Course"


def test_no_token_is_401():
    assert client.get("/units").status_code == 401
    assert client.post("/sessions", json={"unit_id": "x"}).status_code == 401


def test_tampered_or_expired_token_is_401():
    good = _headers()["Authorization"]
    assert client.get("/units", headers={"Authorization": good[:-3] + "abc"}).status_code == 401
    expired = auth.issue_app_token(
        auth.User(sub="t1", name="T", is_staff=True, course_id="course-A", course_title=None), now=0
    )
    assert client.get("/units", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_learner_token_is_403():
    assert client.get("/units", headers=_headers(staff=False)).status_code == 403


def test_units_are_scoped_to_the_course(auth_on):
    unit_id = _make_unit(auth_on, _headers(course="course-A"))
    in_a = client.get("/units", headers=_headers(sub="t2", course="course-A")).json()
    in_b = client.get("/units", headers=_headers(sub="t3", course="course-B")).json()
    assert any(u["id"] == unit_id for u in in_a)
    assert not any(u["id"] == unit_id for u in in_b)
    assert client.get(f"/units/{unit_id}", headers=_headers(course="course-B")).status_code == 404
    # Can't start a session on another course's unit either.
    resp = client.post("/sessions", json={"unit_id": unit_id}, headers=_headers(course="course-B"))
    assert resp.status_code == 404


def test_sessions_belong_to_the_teacher_who_started_them(auth_on):
    owner = _headers(sub="owner", course="course-A")
    other = _headers(sub="colleague", course="course-A")
    session_id = _start(auth_on, _make_unit(auth_on, owner), owner)

    assert client.post(f"/sessions/{session_id}/transcript", json={"text": "hi"}, headers=owner).status_code == 200
    for method, path, body in [
        ("post", f"/sessions/{session_id}/transcript", {"text": "hi"}),
        ("post", f"/sessions/{session_id}/tick", {"force": False}),
        ("post", f"/sessions/{session_id}/activity", None),
        ("post", f"/sessions/{session_id}/note", {"text": "n"}),
        ("post", f"/sessions/{session_id}/end", None),
        ("get", f"/sessions/{session_id}/report", None),
    ]:
        resp = getattr(client, method)(path, json=body, headers=other) if body is not None else getattr(client, method)(path, headers=other)
        assert resp.status_code == 404, f"{path} leaked to another teacher"

    record = session_manager.get_session_record(session_id)
    assert record["owner_sub"] == "owner" and record["course_id"] == "course-A"
    # The owner can still end it and read the report afterwards.
    assert client.post(f"/sessions/{session_id}/end", headers=owner).status_code == 200
    assert client.get(f"/sessions/{session_id}/report", headers=owner).status_code == 200
