"""Self-service revocation of an account's other unexpired login sessions."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import LoginSession, User, get_db, now
from .security import authenticated, digest_token

router = APIRouter(prefix="/api/account/sessions")


@router.get("")
def summary(
    request: Request, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    token_hash = digest_token(request.cookies["nt_session"])
    current = db.get(LoginSession, token_hash)
    count = (
        db.query(LoginSession)
        .filter(
            LoginSession.user_id == u.id,
            LoginSession.token_hash != token_hash,
            LoginSession.expires > now(),
        )
        .count()
    )
    return {"other_active_sessions": count, "current_expires": current.expires}


@router.post("/revoke-others")
def revoke(
    request: Request, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    # Login takes the same account lock, ordering new sign-ins against revocation.
    db.execute(select(User).where(User.id == u.id).with_for_update()).scalar_one()
    token_hash = digest_token(request.cookies["nt_session"])
    # Requery after waiting: another session could have revoked this caller.
    current = db.execute(
        select(LoginSession)
        .where(
            LoginSession.token_hash == token_hash,
            LoginSession.user_id == u.id,
            LoginSession.expires > now(),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(401, "Sign in required")
    count = (
        db.query(LoginSession)
        .filter(
            LoginSession.user_id == u.id,
            LoginSession.token_hash != token_hash,
            LoginSession.expires > now(),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"revoked": count, "current_session_preserved": True}
