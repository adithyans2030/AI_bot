"""Moodle LTI 1.3 launch: how a teacher gets from their Moodle course into
AI Co-host without a separate login.

The flow (IMS LTI 1.3 core, resource-link launch only):

1. Teacher clicks the AI Co-host activity in Moodle. Moodle sends the
   browser to /lti/login (OIDC third-party-initiated login).
2. We remember a one-time `state` + `nonce` (server side, plus a cookie
   that binds the state to this browser) and redirect back to Moodle's
   auth endpoint.
3. Moodle posts a signed `id_token` (RS256 JWT) to /lti/launch. We verify
   the signature against Moodle's public keyset, plus issuer, audience,
   deployment, nonce, expiry, message type and LTI version.
4. Teachers (Instructor / Administrator roles) get an app token and land
   on /app. Anyone else gets a short notice page and no token.

Only the claims needed are used: Moodle's user id, display name, roles and
the course (context) id/title. Email is never requested or stored.
"""
from __future__ import annotations

import hashlib
import html
import secrets
import threading
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm

from . import auth, config

router = APIRouter(prefix="/lti", tags=["lti"])

LTI_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/"
LIS = "http://purl.imsglobal.org/vocab/lis/v2/"

# Roles that may run AI Co-host. Moodle sends full role URIs; teachers
# arrive as membership#Instructor, site admins as institution/system
# Administrator.
STAFF_ROLES = {
    LIS + "membership#Instructor",
    LIS + "membership#Administrator",
    LIS + "membership#ContentDeveloper",
    LIS + "institution/person#Administrator",
    LIS + "system/person#Administrator",
}

STATE_TTL_SECONDS = 600
STATE_COOKIE_PREFIX = "lti_state_"


class LaunchError(Exception):
    pass


# --- One-time state/nonce store (in memory; fine for a single server
# process — move to Redis when running several workers) ---

_states: Dict[str, Tuple[str, float]] = {}
_states_lock = threading.Lock()


def _remember_state(state: str, nonce: str, now: float) -> None:
    with _states_lock:
        for key in [k for k, (_, exp) in _states.items() if exp < now]:
            del _states[key]
        _states[state] = (nonce, now + STATE_TTL_SECONDS)


def _pop_state(state: str, now: float) -> Optional[str]:
    """Return the nonce for this state and forget it (one use only)."""
    with _states_lock:
        entry = _states.pop(state, None)
    if entry is None or entry[1] < now:
        return None
    return entry[0]


# --- Keys ---

_jwks_client: Optional[PyJWKClient] = None


def _platform_signing_key(id_token: str):
    """Moodle's public key for this token, fetched from its keyset URL
    (cached). Separate function so tests can substitute a fake platform."""
    global _jwks_client
    if _jwks_client is None or _jwks_client.uri != config.LTI_PLATFORM_KEYSET_URL:
        _jwks_client = PyJWKClient(config.LTI_PLATFORM_KEYSET_URL, cache_keys=True)
    return _jwks_client.get_signing_key_from_jwt(id_token).key


def _tool_private_key() -> rsa.RSAPrivateKey:
    path = config.LTI_TOOL_PRIVATE_KEY_PATH
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return key


def tool_public_jwk() -> Dict[str, Any]:
    public_key = _tool_private_key().public_key()
    jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    jwk.update({"kid": hashlib.sha256(der).hexdigest()[:16], "alg": "RS256", "use": "sig"})
    return jwk


# --- Validation ---


def _is_configured() -> bool:
    return bool(config.LTI_PLATFORM_ISSUER and config.LTI_CLIENT_ID and config.LTI_DEPLOYMENT_IDS)


def verify_id_token(id_token: str, expected_nonce: str) -> Dict[str, Any]:
    try:
        key = _platform_signing_key(id_token)
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=config.LTI_CLIENT_ID,
            issuer=config.LTI_PLATFORM_ISSUER,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise LaunchError(f"The launch token could not be verified ({exc}).") from exc

    if not secrets.compare_digest(str(claims.get("nonce")), expected_nonce):
        raise LaunchError("The launch token does not match this sign-in attempt.")
    # With several audiences, the authorized party must be this tool.
    if isinstance(claims.get("aud"), list) and claims.get("azp") not in (None, config.LTI_CLIENT_ID):
        raise LaunchError("The launch token was issued for a different tool.")
    if claims.get(LTI_CLAIM + "deployment_id") not in config.LTI_DEPLOYMENT_IDS:
        raise LaunchError("This Moodle deployment is not registered with AI Co-host.")
    if claims.get(LTI_CLAIM + "message_type") != "LtiResourceLinkRequest":
        raise LaunchError("Unsupported LTI message type.")
    if claims.get(LTI_CLAIM + "version") != "1.3.0":
        raise LaunchError("Unsupported LTI version.")
    return claims


def user_from_claims(claims: Dict[str, Any]) -> auth.User:
    roles = set(claims.get(LTI_CLAIM + "roles") or [])
    context = claims.get(LTI_CLAIM + "context") or {}
    if not context.get("id"):
        raise LaunchError("Open AI Co-host from inside a Moodle course.")
    name = claims.get("name") or " ".join(
        p for p in (claims.get("given_name"), claims.get("family_name")) if p
    )
    return auth.User(
        sub=str(claims["sub"]),
        name=name or "Teacher",
        is_staff=bool(roles & STAFF_ROLES),
        course_id=str(context["id"]),
        course_title=context.get("title") or context.get("label"),
    )


# --- Pages ---


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1.5rem;line-height:1.5;color:#222}}
h1{{font-size:1.4rem}}</style></head><body><h1>{html.escape(title)}</h1>{body}</body></html>""",
        status_code=status_code,
    )


def _error_page(message: str, status_code: int = 400) -> HTMLResponse:
    return _page(
        "AI Co-host could not start",
        f"<p>{html.escape(message)}</p><p>Close this window and open the activity again from your "
        "Moodle course. If it keeps happening, ask your Moodle administrator to check that the tool "
        "opens in a new window.</p>",
        status_code,
    )


LEARNER_NOTICE = (
    "<p>AI Co-host is a tool for teachers. During live classes in this course, your teacher may use "
    "a clearly labelled AI assistant that suggests questions about the course material.</p>"
    "<ul><li>It is always labelled as AI and never poses as a student.</li>"
    "<li>It does not record attendance or report on individual students.</li></ul>"
)


# --- Routes ---


@router.api_route("/login", methods=["GET", "POST"])
async def oidc_login(request: Request):
    """Step 1-2: Moodle's login initiation, answered with a redirect to its
    auth endpoint."""
    if not _is_configured():
        return _error_page("AI Co-host is not connected to Moodle yet (LTI settings are missing).", 503)

    params: Dict[str, str] = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        params.update({k: str(v) for k, v in form.items()})

    if params.get("iss", "").rstrip("/") != config.LTI_PLATFORM_ISSUER:
        return _error_page("This launch came from a Moodle site that is not registered.")
    if params.get("client_id") and params["client_id"] != config.LTI_CLIENT_ID:
        return _error_page("This launch is for a different tool registration.")
    if not params.get("login_hint"):
        return _error_page("The launch request is incomplete (missing login_hint).")
    target = params.get("target_link_uri", "")
    if target and not target.startswith(config.TOOL_BASE_URL):
        return _error_page("The launch points to a different address than this server.")

    now = time.time()
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    _remember_state(state, nonce, now)

    query = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "prompt": "none",
        "client_id": config.LTI_CLIENT_ID,
        "redirect_uri": f"{config.TOOL_BASE_URL}/lti/launch",
        "login_hint": params["login_hint"],
        "state": state,
        "nonce": nonce,
    }
    if params.get("lti_message_hint"):
        query["lti_message_hint"] = params["lti_message_hint"]

    response = RedirectResponse(f"{config.LTI_AUTH_LOGIN_URL}?{urlencode(query)}", status_code=302)
    # SameSite=None so the cookie survives Moodle's cross-site form post
    # back to /lti/launch. Browsers accept Secure cookies on localhost too.
    response.set_cookie(
        STATE_COOKIE_PREFIX + state,
        "1",
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="none",
        path="/lti",
    )
    return response


@router.post("/launch")
async def launch(request: Request):
    """Step 3-4: verify Moodle's signed launch and sign the teacher in."""
    if not _is_configured():
        return _error_page("AI Co-host is not connected to Moodle yet (LTI settings are missing).", 503)

    form = await request.form()
    id_token, state = form.get("id_token"), form.get("state")
    if not id_token or not state:
        return _error_page("The launch request is incomplete.")
    id_token, state = str(id_token), str(state)

    nonce = _pop_state(state, time.time())
    if nonce is None:
        return _error_page("This launch has expired or was already used.")
    if request.cookies.get(STATE_COOKIE_PREFIX + state) != "1":
        return _error_page(
            "Your browser did not return the sign-in cookie. This usually means the tool was opened "
            "inside a frame; it needs to open in a new window."
        )

    try:
        claims = verify_id_token(id_token, nonce)
        user = user_from_claims(claims)
    except LaunchError as exc:
        return _error_page(str(exc))

    if not user.is_staff:
        response = _page("About AI Co-host", LEARNER_NOTICE)
    else:
        token = auth.issue_app_token(user)
        # Token travels in the URL fragment, which browsers never send to a
        # server; the app moves it to sessionStorage and strips it at once.
        response = RedirectResponse(f"/app#token={token}", status_code=303)
    response.delete_cookie(STATE_COOKIE_PREFIX + state, path="/lti", secure=True, samesite="none")
    return response


@router.get("/jwks")
def jwks():
    """The tool's public keyset (Moodle asks for this URL at registration)."""
    return {"keys": [tool_public_jwk()]}


@router.get("/setup")
def setup_values():
    """The values a Moodle administrator pastes into Site administration >
    Plugins > External tool > Manage tools > Configure a tool manually."""
    base = config.TOOL_BASE_URL
    return {
        "lti_version": "LTI 1.3",
        "tool_url": f"{base}/lti/launch",
        "public_key_type": "Keyset URL",
        "public_keyset_url": f"{base}/lti/jwks",
        "initiate_login_url": f"{base}/lti/login",
        "redirection_uris": [f"{base}/lti/launch"],
        "default_launch_container": "New window",
        "share_launcher_name": "Always",
        "share_launcher_email": "Never",
        "accept_grades": "Never",
        "configured": _is_configured(),
    }
