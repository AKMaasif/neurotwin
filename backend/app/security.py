"""Prototype sign-in and access rules.

Sign-in is a signed token naming a user. There are no passwords: this prototype only ever holds synthetic
demo accounts, and it must not hold real health data until real authentication replaces this module.

Access rules, in one place:
- A participant sees and manages everything of their own.
- Anyone else needs an active grant from that participant, for the purpose the data serves.
  `clinical_review` (clinicians only) opens the evidence, To check items and audit trail.
  `participation_updates` (family only) opens a summary of which activities were done and when, never values.
- Revoking a grant stops access at once. It deletes nothing.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AccessGrant, User

PURPOSE_ROLE = {"clinical_review": "clinician", "participation_updates": "family"}


def make_token(user_id: str, secret: str) -> str:
    sig = hmac.new(secret.encode(), user_id.encode(), hashlib.sha256).digest()
    return f"{user_id}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def read_token(token: str, secret: str) -> str | None:
    user_id, _, _ = token.rpartition(".")
    if not user_id:
        return None
    return user_id if hmac.compare_digest(make_token(user_id, secret), token) else None


def get_db(request: Request):
    yield from request.app.state.db.session()


def current_user(request: Request, authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not signed in.")
    user_id = read_token(authorization.removeprefix("Bearer "), request.app.state.secret)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(401, "Sign-in is no longer valid.")
    return user


def active_grant(db: Session, owner_id: str, grantee_id: str, purpose: str) -> AccessGrant | None:
    return db.scalar(select(AccessGrant).where(
        AccessGrant.owner_id == owner_id, AccessGrant.grantee_id == grantee_id,
        AccessGrant.purpose == purpose, AccessGrant.revoked_at.is_(None)))


def can_read_evidence(db: Session, user: User, participant_id: str) -> bool:
    if user.id == participant_id:
        return True
    return user.role == "clinician" and active_grant(db, participant_id, user.id, "clinical_review") is not None


def require_evidence_access(db: Session, user: User, participant_id: str) -> None:
    if not can_read_evidence(db, user, participant_id):
        # Same answer whether the person exists or not: no hint about who is in the system.
        raise HTTPException(404, "Not found, or you do not have access.")
