"""Authentication endpoints with brute-force protection."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import User
from ..security import (SESSION_COOKIE, audit, create_session_token, current_user,
                        set_session_cookie, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# in-memory lockout (per username). Process-local by design; documented in the security checklist.
_failures: dict[str, list[float]] = defaultdict(list)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


def _locked(username: str) -> bool:
    s = get_settings()
    window = s.login_lock_minutes * 60
    recent = [t for t in _failures[username] if time.time() - t < window]
    _failures[username] = recent
    return len(recent) >= s.login_max_failures


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    if _locked(body.username):
        raise HTTPException(429, "Too many failed attempts. Try again later.")
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        _failures[body.username].append(time.time())
        audit(db, body.username or "unknown", "login_failed", "")
        raise HTTPException(401, "Invalid username or password")
    _failures.pop(body.username, None)
    set_session_cookie(response, create_session_token(user))
    audit(db, user.username, "login_success", f"role={user.role}")
    return {"username": user.username, "role": user.role, "full_name": user.full_name}


@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role, "full_name": user.full_name}
