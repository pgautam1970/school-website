"""Authentication (PBKDF2 password hashing, signed session cookies) and RBAC.

No third-party auth dependencies: everything here uses hashlib/hmac/secrets so
the system runs on Windows, Linux and Docker without native build tools.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from functools import wraps

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AuditLog, User

PBKDF2_ITERATIONS = 240_000
SESSION_COOKIE = "kvi_session"
SESSION_MAX_AGE = 12 * 3600  # 12 hours

# Role hierarchy: what each role may do.
ROLE_LEVELS = {"viewer": 0, "staff": 1, "leadership": 2, "admin": 3}


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, dk_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ---------------------------------------------------------------- sessions
def _sign(payload: bytes) -> str:
    key = get_settings().secret_key.encode()
    sig = hmac.new(key, payload, hashlib.sha256).digest()
    return urlsafe_b64encode(payload).decode() + "." + urlsafe_b64encode(sig).decode()


def _unsign(token: str) -> bytes | None:
    try:
        payload_b64, sig_b64 = token.split(".")
        payload = urlsafe_b64decode(payload_b64)
        sig = urlsafe_b64decode(sig_b64)
        key = get_settings().secret_key.encode()
        expected = hmac.new(key, payload, hashlib.sha256).digest()
        if hmac.compare_digest(sig, expected):
            return payload
    except Exception:
        pass
    return None


def create_session_token(user: User) -> str:
    payload = json.dumps({
        "uid": user.id, "u": user.username, "r": user.role, "exp": int(time.time()) + SESSION_MAX_AGE,
    }).encode()
    return _sign(payload)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True,
                        samesite="lax", secure=get_settings().env == "production")


def read_session(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    payload = _unsign(token)
    if not payload:
        return None
    data = json.loads(payload)
    if data.get("exp", 0) < time.time():
        return None
    return data


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: require a valid session with an active user."""
    sess = read_session(request)
    if not sess:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get(User, sess["uid"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or missing")
    if user.role != sess.get("r"):
        # role changed since login — force re-login
        raise HTTPException(status_code=401, detail="Role changed; please log in again")
    return user


def require_role(min_role: str):
    """Dependency factory enforcing a minimum role level."""
    def dep(user: User = Depends(current_user)) -> User:
        if ROLE_LEVELS.get(user.role, -1) < ROLE_LEVELS[min_role]:
            raise HTTPException(status_code=403, detail=f"Requires role '{min_role}' or higher")
        return user
    return dep


def audit(db: Session, username: str, action: str, detail: str = "") -> None:
    db.add(AuditLog(username=username, action=action, detail=detail[:2000]))
    db.commit()
