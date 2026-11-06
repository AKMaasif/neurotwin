import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Grant, LoginSession, Patient, User, get_db, now


def password_hash(password: str, salt: str | None = None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
    ).hex()
    return f"{salt}:{digest}"


def password_matches(password, encoded):
    return hmac.compare_digest(password_hash(password, encoded.split(":")[0]), encoded)


def digest_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def authenticated(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("nt_session", "")
    row = db.get(LoginSession, digest_token(token))
    if not row or row.expires <= now():
        raise HTTPException(401, "Sign in required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), row.csrf):
            raise HTTPException(403, "Invalid CSRF token")
    actor = db.get(User, row.user_id)
    if request.headers.get("x-expected-actor") not in (None, actor.id):
        raise HTTPException(409, "Session account changed; sign in again")
    request.state.actor_id = actor.id
    bind_actor(db, actor.id)
    return actor


def bind_actor(db, actor_id):
    db.info["care_actor"] = actor_id
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(
            text("SELECT set_config('neurotwin.actor_id', :actor, true)"),
            {"actor": actor_id},
        )


def authorize(db, actor, patient_id, scope):
    # Serialize commands on the patient row in PostgreSQL. This also orders
    # revocation against in-flight sends and prevents duplicate command races.
    p = db.execute(
        select(Patient).where(Patient.id == patient_id).with_for_update()
    ).scalar_one_or_none()
    grant = (
        db.query(Grant)
        .filter_by(user_id=actor.id, patient_id=patient_id, active=True)
        .first()
    )
    if not p or p.org != actor.org or not grant or scope not in grant.scopes:
        raise HTTPException(403, "Access not granted")
    return p
