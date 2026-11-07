"""Current-password-verified change, followed by sign-out of all own sessions."""

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .db import LoginSession, User, get_db, now
from .security import authenticated, digest_token, password_hash, password_matches

router = APIRouter(prefix="/api/account")


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    current_password: str = Field(min_length=1, max_length=300, repr=False)
    new_password: str = Field(min_length=15, max_length=300, repr=False)


@router.post("/password")
async def change_password(
    request: Request,
    response: Response,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import attempts

    if (
        request.headers.get("content-type", "").split(";")[0].strip().lower()
        != "application/json"
    ):
        raise HTTPException(415, "Use a JSON password-change request")
    # FastAPI's default body-validation response can echo input values. Keep
    # credential validation local and return a fixed message without passwords.
    try:
        body = PasswordChange.model_validate(await request.json())
        body.current_password.encode("utf-8")
        body.new_password.encode("utf-8")
        if not body.new_password.strip():
            raise ValueError("Blank password")
    except (ValueError, TypeError, RecursionError):
        raise HTTPException(
            422,
            "Provide your current password and a new password of 15 to 300 characters",
        ) from None
    queue = attempts[(request.client.host, u.id, "password-change")]
    stamp = time.monotonic()
    while queue and queue[0] < stamp - 60:
        queue.popleft()
    if len(queue) >= 5:
        raise HTTPException(429, "Try again later")
    queue.append(stamp)

    def update_credentials():
        actor = db.execute(
            select(User)
            .where(User.id == u.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        current = db.execute(
            select(LoginSession)
            .where(
                LoginSession.token_hash == digest_token(request.cookies["nt_session"]),
                LoginSession.user_id == actor.id,
                LoginSession.expires > now(),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if current is None:
            raise HTTPException(401, "Sign in required")
        if not password_matches(body.current_password, actor.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        if body.new_password == body.current_password:
            raise HTTPException(
                422, "Choose a password different from your current password"
            )
        actor.password_hash = password_hash(body.new_password)
        db.query(LoginSession).filter(LoginSession.user_id == actor.id).delete(
            synchronize_session=False
        )
        db.commit()

    await run_in_threadpool(update_credentials)
    response.delete_cookie("nt_session")
    return {"status": "password_changed", "signed_out": True}
