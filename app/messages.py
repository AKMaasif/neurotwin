"""Patient-bound, direct in-app messages. No external delivery or automatic reading."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Audit, CareMessage, Grant, User, get_db, now
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/messages", tags=["care messages"])
ROLES = {"participant", "family", "clinician"}


def access(db, u, pid):
    authorize(db, u, pid, "messages")
    if u.role not in ROLES:
        raise HTTPException(403, "Care-circle messaging is not available for this role")


def peer(db, u, pid, peer_id):
    access(db, u, pid)
    target = db.get(User, peer_id)
    if (
        not target
        or target.id == u.id
        or target.org != u.org
        or target.role not in ROLES
    ):
        raise HTTPException(403, "Contact is not available for this patient")
    authorize(db, target, pid, "messages")
    return target


def pair_query(db, pid, a, b):
    return db.query(CareMessage).filter(
        CareMessage.patient_id == pid,
        or_(
            and_(CareMessage.sender_id == a, CareMessage.recipient_id == b),
            and_(CareMessage.sender_id == b, CareMessage.recipient_id == a),
        ),
    )


def pack(row, actor):
    return {
        "id": row.id,
        "sender_id": row.sender_id,
        "recipient_id": row.recipient_id,
        "body": row.body,
        "created_at": row.created_at,
        "opened_at": row.opened_at,
        "state": "opened_in_app" if row.opened_at else "saved_in_app",
        "command_id": row.command_id if row.sender_id == actor.id else None,
    }


@router.get("/inbox")
def inbox(pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    access(db, u, pid)
    contacts = [
        (person, grant)
        for person, grant in db.query(User, Grant)
        .join(Grant, Grant.user_id == User.id)
        .filter(
            Grant.patient_id == pid,
            Grant.active.is_(True),
            User.org == u.org,
            User.id != u.id,
            User.role.in_(ROLES),
        )
        .order_by(User.name, User.id)
        .all()
        if "messages" in grant.scopes
    ]
    ids = [person.id for person, _ in contacts]
    received = dict(
        db.query(CareMessage.sender_id, func.count(CareMessage.id))
        .filter(
            CareMessage.patient_id == pid,
            CareMessage.recipient_id == u.id,
            CareMessage.sender_id.in_(ids),
            CareMessage.opened_at.is_(None),
        )
        .group_by(CareMessage.sender_id)
        .all()
    )
    own = (
        db.query(
            func.count(CareMessage.id),
            func.max(CareMessage.created_at),
            func.max(CareMessage.opened_at),
            func.count(CareMessage.opened_at),
        )
        .filter(
            CareMessage.patient_id == pid,
            or_(
                and_(CareMessage.sender_id == u.id, CareMessage.recipient_id.in_(ids)),
                and_(CareMessage.recipient_id == u.id, CareMessage.sender_id.in_(ids)),
            ),
        )
        .one()
    )
    revision = hashlib.sha256(
        json.dumps(
            [
                list(own),
                [(person.id, person.name, person.role) for person, _ in contacts],
                sorted(received.items()),
            ]
        ).encode()
    ).hexdigest()
    return {
        "contacts": [
            {
                "id": person.id,
                "name": person.name,
                "role": person.role,
                "unopened": received.get(person.id, 0),
            }
            for person, _ in contacts
        ],
        "unopened": sum(received.values()),
        "revision": revision,
        "as_of": now(),
    }


@router.get("/threads/{peer_id}")
def thread(
    pid: str,
    peer_id: str,
    before: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=40, ge=1, le=100),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    query = pair_query(db, pid, u.id, target.id)
    if before:
        cursor = query.filter(CareMessage.id == before).first()
        if not cursor:
            raise HTTPException(404, "Conversation cursor is not available")
        query = query.filter(
            or_(
                CareMessage.created_at < cursor.created_at,
                and_(
                    CareMessage.created_at == cursor.created_at,
                    CareMessage.id < cursor.id,
                ),
            )
        )
    rows = (
        query.order_by(CareMessage.created_at.desc(), CareMessage.id.desc())
        .limit(limit + 1)
        .all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "contact": {"id": target.id, "name": target.name, "role": target.role},
        "messages": [pack(r, u) for r in reversed(rows)],
        "next_before": rows[-1].id if more else None,
        "as_of": now(),
    }


class Send(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def readable_text(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("Enter a text message without control characters")
        return value


class Opened(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/threads/{peer_id}")
def send(
    pid: str,
    peer_id: str,
    body: Send,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    existing = (
        db.query(CareMessage)
        .filter_by(sender_id=u.id, command_id=body.command_id)
        .first()
    )
    if existing:
        if (existing.patient_id, existing.recipient_id, existing.body) != (
            pid,
            target.id,
            body.body,
        ):
            raise HTTPException(
                409, "Message command was already used for different content"
            )
        return pack(existing, u)
    row = CareMessage(
        patient_id=pid,
        sender_id=u.id,
        recipient_id=target.id,
        body=body.body,
        command_id=body.command_id,
    )
    try:
        db.add(row)
        db.flush()
        db.add(
            Audit(
                patient_id=pid,
                actor=u.id,
                action="message.saved",
                detail={"message_id": row.id, "recipient_id": target.id},
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Message command changed concurrently; refresh the conversation"
        ) from None
    return pack(row, u)


@router.post("/threads/{peer_id}/opened")
def opened(
    pid: str,
    peer_id: str,
    body: Opened,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    ids = set(body.message_ids)
    rows = (
        pair_query(db, pid, target.id, u.id)
        .filter(CareMessage.id.in_(ids), CareMessage.recipient_id == u.id)
        .all()
    )
    if len(rows) != len(ids):
        raise HTTPException(404, "One or more incoming messages are not available")
    changed = [r for r in rows if not r.opened_at]
    at = now()
    for row in changed:
        row.opened_at = at
    if changed:
        db.add(
            Audit(
                patient_id=pid,
                actor=u.id,
                action="message.opened",
                detail={
                    "message_ids": sorted(r.id for r in changed),
                    "evidence": "explicit recipient acknowledgement; not proof of comprehension",
                },
            )
        )
    db.commit()
    return {"acknowledged": len(changed), "messages": [pack(r, u) for r in rows]}
