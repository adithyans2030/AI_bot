"""Moodle LTI 1.3 launch, end to end, against a simulated Moodle.

The test plays Moodle: it has its own RSA key, signs id_tokens exactly as
Moodle would, and the tool's keyset lookup is pointed at that key instead
of fetching https://<moodle>/mod/lti/certs.php. Everything else (state,
cookie, nonce, claim checks, role handling, app-token issue) is the real
code path.
"""
from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import auth, config, lti
from app.main import app

ISSUER = "https://moodle.test"
CLIENT_ID = "client-abc"
DEPLOYMENT_ID = "1"
TOOL = "http://testserver"
LIS = "http://purl.imsglobal.org/vocab/lis/v2/"
CLAIM = "https://purl.imsglobal.org/spec/lti/claim/"

PLATFORM_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def lti_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LTI_PLATFORM_ISSUER", ISSUER)
    monkeypatch.setattr(config, "LTI_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(config, "LTI_DEPLOYMENT_IDS", [DEPLOYMENT_ID])
    monkeypatch.setattr(config, "LTI_AUTH_LOGIN_URL", f"{ISSUER}/mod/lti/auth.php")
    monkeypatch.setattr(config, "TOOL_BASE_URL", TOOL)
    monkeypatch.setattr(config, "APP_SECRET", "test-secret-" + "x" * 32)
    monkeypatch.setattr(config, "LTI_TOOL_PRIVATE_KEY_PATH", tmp_path / "tool_key.pem")
    monkeypatch.setattr(lti, "_platform_signing_key", lambda token: PLATFORM_KEY.public_key())


def _client():
    # Plain http test server: send the Secure state cookie by hand, the way
    # a browser would on https (or on localhost).
    return TestClient(app, follow_redirects=False)


def _login(client, **overrides):
    params = {
        "iss": ISSUER,
        "login_hint": "42",
        "target_link_uri": f"{TOOL}/lti/launch",
        "lti_message_hint": "hint-123",
        "client_id": CLIENT_ID,
        "lti_deployment_id": DEPLOYMENT_ID,
    }
    params.update(overrides)
    return client.post("/lti/login", data=params)


def _state_and_nonce(login_response):
    query = parse_qs(urlparse(login_response.headers["location"]).query)
    return query["state"][0], query["nonce"][0]


def _id_token(nonce, *, roles=None, key=PLATFORM_KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "42",
        "iat": now,
        "exp": now + 300,
        "nonce": nonce,
        "name": "Dr. Test Teacher",
        CLAIM + "deployment_id": DEPLOYMENT_ID,
        CLAIM + "message_type": "LtiResourceLinkRequest",
        CLAIM + "version": "1.3.0",
        CLAIM + "roles": roles if roles is not None else [LIS + "membership#Instructor"],
        CLAIM + "context": {"id": "course-7", "title": "Data Structures"},
        CLAIM + "resource_link": {"id": "rl-1"},
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "moodle-key"})


def _launch(client, state, id_token, with_cookie=True):
    headers = {"cookie": f"{lti.STATE_COOKIE_PREFIX}{state}=1"} if with_cookie else {}
    return client.post("/lti/launch", data={"id_token": id_token, "state": state}, headers=headers)


def test_login_redirects_to_moodle_auth_with_state_nonce_and_cookie():
    client = _client()
    resp = _login(client)
    assert resp.status_code == 302
    location = urlparse(resp.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == f"{ISSUER}/mod/lti/auth.php"
    query = parse_qs(location.query)
    assert query["redirect_uri"] == [f"{TOOL}/lti/launch"]
    assert query["client_id"] == [CLIENT_ID]
    assert query["login_hint"] == ["42"]
    assert query["lti_message_hint"] == ["hint-123"]
    assert query["response_mode"] == ["form_post"]
    state = query["state"][0]
    cookie = resp.headers["set-cookie"]
    assert f"{lti.STATE_COOKIE_PREFIX}{state}=1" in cookie
    assert "secure" in cookie.lower() and "samesite=none" in cookie.lower()


def test_login_also_accepts_get():
    resp = _client().get("/lti/login", params={"iss": ISSUER, "login_hint": "42"})
    assert resp.status_code == 302


def test_login_rejects_unknown_platform():
    resp = _login(_client(), iss="https://evil.example")
    assert resp.status_code == 400


def test_login_rejects_foreign_target_link():
    resp = _login(_client(), target_link_uri="https://elsewhere.example/launch")
    assert resp.status_code == 400


def test_teacher_launch_signs_in_and_lands_on_app():
    client = _client()
    state, nonce = _state_and_nonce(_login(client))
    resp = _launch(client, state, _id_token(nonce))
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/app#token=")

    user = auth.decode_app_token(location.split("token=", 1)[1])
    assert user.sub == "42"
    assert user.name == "Dr. Test Teacher"
    assert user.is_staff is True
    assert user.course_id == "course-7"
    assert user.course_title == "Data Structures"


def test_learner_launch_gets_notice_and_no_token():
    client = _client()
    state, nonce = _state_and_nonce(_login(client))
    resp = _launch(client, state, _id_token(nonce, roles=[LIS + "membership#Learner"]))
    assert resp.status_code == 200
    assert "token" not in resp.headers.get("location", "")
    assert "never poses as a student" in resp.text
    assert "does not record attendance" in resp.text


def test_site_admin_counts_as_staff():
    client = _client()
    state, nonce = _state_and_nonce(_login(client))
    resp = _launch(client, state, _id_token(nonce, roles=[LIS + "institution/person#Administrator"]))
    assert resp.status_code == 303


def test_state_can_only_be_used_once():
    client = _client()
    state, nonce = _state_and_nonce(_login(client))
    assert _launch(client, state, _id_token(nonce)).status_code == 303
    replay = _launch(client, state, _id_token(nonce))
    assert replay.status_code == 400
    assert "expired or was already used" in replay.text


def test_launch_without_state_cookie_is_rejected():
    client = _client()
    state, nonce = _state_and_nonce(_login(client))
    resp = _launch(client, state, _id_token(nonce), with_cookie=False)
    assert resp.status_code == 400
    assert "new window" in resp.text


@pytest.mark.parametrize(
    "overrides, key",
    [
        ({"nonce": "wrong-nonce"}, PLATFORM_KEY),
        ({"aud": "some-other-tool"}, PLATFORM_KEY),
        ({"iss": "https://evil.example"}, PLATFORM_KEY),
        ({CLAIM + "deployment_id": "999"}, PLATFORM_KEY),
        ({CLAIM + "message_type": "LtiDeepLinkingRequest"}, PLATFORM_KEY),
        ({CLAIM + "version": "1.1"}, PLATFORM_KEY),
        ({"exp": int(time.time()) - 3600}, PLATFORM_KEY),
        ({CLAIM + "context": {}}, PLATFORM_KEY),
        ({}, OTHER_KEY),  # signed by someone other than Moodle
    ],
    ids=["nonce", "audience", "issuer", "deployment", "message-type", "version", "expired", "no-course", "forged"],
)
def test_bad_launch_tokens_are_rejected(overrides, key):
    client = _client()
    state, nonce = _state_and_nonce(_login(client))
    token_overrides = dict(overrides)
    token_nonce = token_overrides.pop("nonce", nonce)
    resp = _launch(client, state, _id_token(token_nonce, key=key, **token_overrides))
    assert resp.status_code == 400
    assert "location" not in resp.headers


def test_unconfigured_tool_refuses_launch(monkeypatch):
    monkeypatch.setattr(config, "LTI_CLIENT_ID", "")
    resp = _login(_client())
    assert resp.status_code == 503


def test_jwks_serves_tool_public_key():
    keys = _client().get("/lti/jwks").json()["keys"]
    assert len(keys) == 1
    key = keys[0]
    assert key["kty"] == "RSA" and key["alg"] == "RS256" and key["use"] == "sig"
    assert "d" not in key  # never the private part
    # Stable across calls (key persisted, not regenerated).
    assert _client().get("/lti/jwks").json()["keys"][0]["kid"] == key["kid"]


def test_setup_values_for_moodle_admin():
    values = _client().get("/lti/setup").json()
    assert values["initiate_login_url"] == f"{TOOL}/lti/login"
    assert values["public_keyset_url"] == f"{TOOL}/lti/jwks"
    assert values["default_launch_container"] == "New window"
    assert values["share_launcher_email"] == "Never"
