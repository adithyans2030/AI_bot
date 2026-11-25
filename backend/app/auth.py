"""App-level authentication: who is calling, and are they allowed to.

Identity comes only from a verified Moodle LTI 1.3 launch (see lti.py).
A successful teacher launch is exchanged for a short-lived app token
(HS256 JWT signed with APP_SECRET), which the frontend sends back as
`Authorization: Bearer <token>` on every API call.

When config.AUTH_REQUIRED is off (local development, the test suite), any
caller is treated as a local developer with full access, so the prototype
keeps working without a Moodle. Turn it on for every real deployment.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException

from . import config

APP_TOKEN_ISSUER = "ai-cohost"


@dataclass(frozen=True)
class User:
    sub: str
    name: str
    is_staff: bool
    course_id: Optional[str]
    course_title: Optional[str]
    authenticated: bool = True


# Used only when AUTH_REQUIRED is off and no valid token was sent.
DEV_USER = User(
    sub="local-dev",
    name="Local developer",
    is_staff=True,
    course_id=None,
    course_title=None,
    authenticated=False,
)

_secret_cache: Optional[str] = None


def app_secret() -> str:
    """APP_SECRET from .env, else a random secret generated once and kept
    under data/lti/ so tokens survive a server restart."""
    global _secret_cache
    if config.APP_SECRET:
        return config.APP_SECRET
    if _secret_cache:
        return _secret_cache
    path = config.LTI_DIR / "app_secret"
    if path.exists():
        _secret_cache = path.read_text(encoding="utf-8").strip()
    else:
        config.LTI_DIR.mkdir(parents=True, exist_ok=True)
        _secret_cache = secrets.token_urlsafe(48)
        path.write_text(_secret_cache, encoding="utf-8")
    return _secret_cache


def issue_app_token(user: User, now: Optional[float] = None) -> str:
    now = now if now is not None else time.time()
    payload = {
        "iss": APP_TOKEN_ISSUER,
        "sub": user.sub,
        "name": user.name,
        "staff": user.is_staff,
        "course_id": user.course_id,
        "course_title": user.course_title,
        "iat": int(now),
        "exp": int(now + config.APP_TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, app_secret(), algorithm="HS256")


def decode_app_token(token: str) -> User:
    """Raises jwt.PyJWTError if the token is invalid, tampered or expired."""
    claims = jwt.decode(
        token,
        app_secret(),
        algorithms=["HS256"],
        issuer=APP_TOKEN_ISSUER,
        options={"require": ["exp", "iat", "iss", "sub"]},
    )
    return User(
        sub=str(claims["sub"]),
        name=str(claims.get("name") or "Teacher"),
        is_staff=bool(claims.get("staff")),
        course_id=claims.get("course_id"),
        course_title=claims.get("course_title"),
    )


def optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[User]:
    """The caller's identity if a valid app token was sent, else None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        return decode_app_token(authorization[7:].strip())
    except jwt.PyJWTError:
        return None


def require_teacher(user: Optional[User] = Depends(optional_user)) -> User:
    if not config.AUTH_REQUIRED:
        return user or DEV_USER
    if user is None:
        raise HTTPException(401, "Not signed in. Open AI Co-host from your Moodle course.")
    if not user.is_staff:
        raise HTTPException(403, "AI Co-host is only available to teachers.")
    return user


def can_see_course_item(user: User, item_course_id: Optional[str]) -> bool:
    """Units belong to the Moodle course they were created in. A signed-in
    teacher sees only their current course's units; the local developer
    (auth off, no token) sees everything."""
    if not user.authenticated:
        return True
    return item_course_id == user.course_id


def can_see_session(user: User, session: dict) -> bool:
    """A session is visible only to the teacher who started it (the local
    developer, who only exists while auth is off, sees everything)."""
    if not user.authenticated:
        return True
    return session.get("owner_sub") == user.sub
