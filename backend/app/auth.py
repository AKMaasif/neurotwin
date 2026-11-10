"""Sign-in, sign-out, the current session, and account settings (password, other signed-in devices)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import services as S
from .models import LoginSession, User
from .security import (COOKIE, Attempts, current_user, digest, get_db, hash_password, password_matches,
                       password_problem, session_from, start_session, utcnow)

router = APIRouter()
login_attempts = Attempts(limit=5, window_s=60)
password_attempts = Attempts(limit=5, window_s=60)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=300, repr=False)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=300, repr=False)
    new_password: str = Field(min_length=1, max_length=300, repr=False)


def user_out(u: User, own: bool = False) -> dict:
    """A person as others see them. Usernames are shown only to their owner: they are half of a sign-in."""
    out = {"id": u.id, "display_name": u.display_name, "role": u.role, "language": u.language, "is_demo": u.is_demo}
    if own:
        out["username"] = u.username
    return out


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_cookie(request: Request, response: Response, token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=settings["secure_cookies"],
                        max_age=int(settings["session_hours"] * 3600), path="/")


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    key = (_client(request), username)
    if login_attempts.blocked(key):
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
    user = db.scalar(select(User).where(func.lower(User.username) == username))
    if not password_matches(body.password, user.password_hash if user else None):
        login_attempts.fail(key)
        # One message for a wrong username and a wrong password: no hint about which accounts exist.
        raise HTTPException(401, "That username and password do not match.")
    login_attempts.clear(key)
    old = session_from(request, db)
    if old is not None:
        db.delete(old)                     # a new sign-in on this browser replaces its old session
    token, row = start_session(db, user, request.app.state.settings["session_hours"])
    S.audit(db, user.id, "auth.signed_in", user.id if user.role == "participant" else None)
    db.commit()
    _set_cookie(request, response, token)
    return {"user": user_out(user, own=True), "csrf": row.csrf}


@router.get("/api/auth/session")
def session(request: Request, user: User = Depends(current_user)):
    """Who is signed in on this browser, and the CSRF token the page sends with every change."""
    return {"user": user_out(user, own=True), "csrf": request.state.session.csrf,
            "expires_at": request.state.session.expires_at.isoformat()}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(LoginSession).where(LoginSession.token_hash == request.state.session.token_hash))
    S.audit(db, user.id, "auth.signed_out", user.id if user.role == "participant" else None)
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.post("/api/account/password")
def change_password(body: PasswordIn, request: Request, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    key = (_client(request), user.id)
    if password_attempts.blocked(key):
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
    if not password_matches(body.current_password, user.password_hash):
        password_attempts.fail(key)
        raise HTTPException(400, "Your current password is not right.")
    problem = password_problem(body.new_password, body.current_password)
    if problem:
        raise HTTPException(422, problem)
    password_attempts.clear(key)
    user.password_hash = hash_password(body.new_password)
    current = request.state.session.token_hash
    ended = db.execute(delete(LoginSession).where(LoginSession.user_id == user.id,
                                                  LoginSession.token_hash != current)).rowcount
    S.audit(db, user.id, "account.password_changed", user.id if user.role == "participant" else None)
    db.commit()
    return {"ok": True, "other_sessions_ended": ended}


@router.get("/api/account/sessions")
def other_sessions(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    current = request.state.session
    others = db.scalar(select(func.count()).select_from(LoginSession).where(
        LoginSession.user_id == user.id, LoginSession.token_hash != current.token_hash,
        LoginSession.expires_at > utcnow()))
    return {"other_active_sessions": others, "current_expires_at": current.expires_at.isoformat()}


@router.post("/api/account/sessions/revoke-others")
def revoke_others(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ended = db.execute(delete(LoginSession).where(LoginSession.user_id == user.id,
                                                  LoginSession.token_hash != request.state.session.token_hash)).rowcount
    S.audit(db, user.id, "account.sessions_revoked", user.id if user.role == "participant" else None)
    db.commit()
    return {"ended": ended}


__all__ = ["router", "login_attempts", "password_attempts", "user_out", "digest"]
