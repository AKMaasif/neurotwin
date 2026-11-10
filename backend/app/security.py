"""Sign-in, sessions and access rules.

Passwords
- Stored as scrypt hashes with a random salt, in a self-describing format (`scrypt$n$r$p$salt$hash`) so the cost can
  be raised later without breaking existing passwords. The plain password is never stored or logged.
- Checking an unknown username still runs one scrypt, so the response time does not reveal which usernames exist.
- New passwords are 15 to 300 characters. Length, not composition rules: easier for older adults to remember a
  phrase, harder to guess.

Sessions
- Signing in creates a random token. The browser keeps it in an HttpOnly, SameSite=Strict cookie that page scripts
  cannot read; the database keeps only its SHA-256 hash.
- Every request that changes something must also send the session's CSRF token in the `X-CSRF-Token` header.
- Sessions expire after NEUROTWIN_SESSION_HOURS. Signing out deletes the session. Changing a password signs out
  every other session of that account.
- Five failed sign-ins per minute for one username from one address are allowed; after that, wait a minute.

Access rules, in one place
- A participant sees and manages everything of their own.
- Anyone else needs an active grant from that participant, for the purpose the data serves.
  `clinical_review` (clinicians only) opens the evidence, To check items and audit trail.
  `participation_updates` (family only) opens a summary of which activities were done and when, never values.
- Revoking a grant stops access at once. It deletes nothing.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import AccessGrant, LoginSession, User

PURPOSE_ROLE = {"clinical_review": "clinician", "participation_updates": "family"}
COOKIE = "nt_session"
CSRF_HEADER = "x-csrf-token"
PASSWORD_MIN, PASSWORD_MAX = 15, 300
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_N, _R, _P = 2 ** 14, 8, 1


# ---- Passwords -----------------------------------------------------------------------------------------------

def hash_password(password: str, salt: bytes | None = None, n: int = _N, r: int = _R, p: int = _P) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str | None) -> bool:
    if not encoded:
        hash_password(password)          # same work as a real check: no timing hint that the account is missing
        return False
    try:
        algo, n, r, p, salt, _ = encoded.split("$")
        if algo != "scrypt":
            return False
        candidate = hash_password(password, bytes.fromhex(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, encoded)


def password_problem(new: str, current: str | None = None) -> str | None:
    if not (PASSWORD_MIN <= len(new) <= PASSWORD_MAX) or not new.strip():
        return f"Choose a password of {PASSWORD_MIN} to {PASSWORD_MAX} characters. A short phrase works well."
    if current is not None and new == current:
        return "Choose a password different from your current one."
    return None


# ---- Rate limit ----------------------------------------------------------------------------------------------

class Attempts:
    """Failed attempts per key in a sliding minute. In memory: one server process, which is what the prototype runs."""

    def __init__(self, limit: int = 5, window_s: float = 60):
        self.limit, self.window = limit, window_s
        self._seen: dict[tuple, deque] = defaultdict(deque)

    def blocked(self, key: tuple) -> bool:
        q = self._seen[key]
        cutoff = time.monotonic() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return len(q) >= self.limit

    def fail(self, key: tuple) -> None:
        self._seen[key].append(time.monotonic())

    def clear(self, key: tuple) -> None:
        self._seen.pop(key, None)


# ---- Sessions ------------------------------------------------------------------------------------------------

def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)   # SQLite returns naive datetimes


def start_session(db: Session, user: User, hours: float) -> tuple[str, LoginSession]:
    db.execute(delete(LoginSession).where(LoginSession.expires_at < utcnow()))
    token = secrets.token_urlsafe(32)
    row = LoginSession(token_hash=digest(token), user_id=user.id, csrf=secrets.token_urlsafe(24),
                       expires_at=utcnow() + timedelta(hours=hours))
    db.add(row)
    return token, row


def session_from(request: Request, db: Session) -> LoginSession | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = db.get(LoginSession, digest(token))
    if row is None or aware(row.expires_at) <= utcnow():
        return None
    return row


def get_db(request: Request):
    yield from request.app.state.db.session()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    row = session_from(request, db)
    if row is None:
        raise HTTPException(401, "Please sign in.")
    if request.method not in SAFE_METHODS and not hmac.compare_digest(request.headers.get(CSRF_HEADER, ""), row.csrf):
        raise HTTPException(403, "This request could not be verified. Reload the page and try again.")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(401, "Please sign in.")
    request.state.session = row
    return user


# ---- Access rules --------------------------------------------------------------------------------------------

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
