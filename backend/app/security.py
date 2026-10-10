"""Authentication, authorization, and rate limiting.

Sessions are stateless HMAC-signed tokens stored in an httpOnly cookie
(``purplesol_session``). The frontend reaches the API through a same-origin
proxy, so the cookie is first-party and works on mobile Safari. Bearer tokens
with the same format are accepted for scripts.

State-changing requests authenticated by cookie must carry the
``X-PurpleSol-CSRF: 1`` header; browsers cannot send that cross-site without a
CORS preflight that our CORS policy rejects.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import ROLE_ADMIN, User

SESSION_COOKIE = "purplesol_session"
CSRF_HEADER = "x-purplesol-csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# ── Password hashing (stdlib scrypt) ─────────────────────────────

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, digest_hex = stored.split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ── Session tokens ───────────────────────────────────────────────


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: bytes) -> str:
    return _b64(hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).digest())


def issue_token(user: User, ttl_seconds: Optional[int] = None) -> str:
    ttl = ttl_seconds or settings.session_ttl_hours * 3600
    body = {"uid": str(user.id), "sv": user.session_version, "exp": int(time.time()) + ttl}
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload.encode())}"


def decode_token(token: str) -> Optional[dict]:
    try:
        payload, sig = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload.encode())):
        return None
    try:
        body = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict) or body.get("exp", 0) < time.time():
        return None
    return body


# ── Dependencies ─────────────────────────────────────────────────


@dataclass
class AuthContext:
    user: User
    via_cookie: bool


async def _resolve_user(request: Request, db: AsyncSession) -> Optional[AuthContext]:
    token = None
    via_cookie = False
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    elif SESSION_COOKIE in request.cookies:
        token = request.cookies[SESSION_COOKIE]
        via_cookie = True
    if not token:
        return None
    body = decode_token(token)
    if not body:
        return None
    try:
        uid = uuid.UUID(body["uid"])
    except (KeyError, ValueError):
        return None
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user or not user.is_active or user.session_version != body.get("sv"):
        return None
    return AuthContext(user=user, via_cookie=via_cookie)


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    ctx = await _resolve_user(request, db)
    if ctx is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if ctx.via_cookie and request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")
    request.state.user_id = str(ctx.user.id)
    return ctx.user


async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return user


async def ingest_principal(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    """Event ingestion: an admin session or the INGEST_API_KEY header."""
    key = request.headers.get("x-api-key")
    if key and settings.ingest_api_key and hmac.compare_digest(key, settings.ingest_api_key):
        return "api-key"
    ctx = await _resolve_user(request, db)
    if ctx is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if ctx.via_cookie and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")
    if ctx.user.role != ROLE_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return f"user:{ctx.user.id}"


# ── Rate limiting (in-process sliding window) ────────────────────


class RateLimiter:
    """Sliding-window limiter keyed by client. Per process: with several API
    replicas each enforces its own window (documented limitation)."""

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry = int(window_seconds - (now - hits[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many requests, try again later",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # Railway/Vercel put the original client first in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
