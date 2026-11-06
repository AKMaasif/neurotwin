"""Patient-bound, direct in-app messages. No external delivery or automatic reading."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .care_domain import attach_to_message, conversation, conversation_id, emit, enrich
from .db import (
    Audit,
    CareAttachment,
    CareMessage,
    Grant,
    User,
    get_db,
    now,
)
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
        "body": "Message withdrawn" if row.withdrawn_at else row.body,
        "message_type": "system"
        if row.withdrawn_at
        else "voice"
        if row.media
        else "text",
        "voice": (
            row.media
            | {"url": f"/api/patients/{row.patient_id}/messages/voice/{row.id}"}
        )
        if row.media and not row.withdrawn_at
        else None,
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
            CareMessage.withdrawn_at.is_(None),
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
            func.max(CareMessage.withdrawn_at),
            func.count(CareMessage.withdrawn_at),
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
    from sqlalchemy import case

    latest_rows = (
        db.query(
            CareMessage,
            func.row_number()
            .over(
                partition_by=case(
                    (CareMessage.sender_id == u.id, CareMessage.recipient_id),
                    else_=CareMessage.sender_id,
                ),
                order_by=(CareMessage.created_at.desc(), CareMessage.id.desc()),
            )
            .label("position"),
        )
        .filter(
            CareMessage.patient_id == pid,
            or_(
                and_(CareMessage.sender_id == u.id, CareMessage.recipient_id.in_(ids)),
                and_(CareMessage.recipient_id == u.id, CareMessage.sender_id.in_(ids)),
            ),
        )
        .subquery()
    )
    latest = {}
    for r in db.query(latest_rows).filter(latest_rows.c.position == 1):
        other = r.recipient_id if r.sender_id == u.id else r.sender_id
        latest[other] = {
            "id": r.id,
            "preview": "Message withdrawn"
            if r.withdrawn_at
            else r.body[:100] or "Attachment",
            "created_at": r.created_at,
            "outgoing": r.sender_id == u.id,
            "opened": bool(r.opened_at),
        }
    return {
        "contacts": [
            {
                "id": person.id,
                "name": person.name,
                "role": person.role,
                "unopened": received.get(person.id, 0),
                "last_message": latest.get(person.id),
                "conversation_id": conversation_id(pid, u.id, person.id),
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
    q: str = Query(default="", max_length=120),
    kind: str = Query(default="", max_length=20),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    conv = conversation(db, pid, u, target)
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
    if q:
        term = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            CareMessage.withdrawn_at.is_(None),
            CareMessage.body.ilike("%" + term + "%", escape="\\"),
        )
    if kind:
        if kind not in {"text", "voice", "audio", "image", "video", "document"}:
            raise HTTPException(422, "Unsupported message filter")
        query = query.filter(CareMessage.withdrawn_at.is_(None))
        if kind == "voice":
            query = query.filter(
                or_(
                    CareMessage.media["content_type"].as_string().is_not(None),
                    CareMessage.id.in_(
                        db.query(CareAttachment.message_id).filter(
                            CareAttachment.kind == "voice",
                            CareAttachment.status == "committed",
                        )
                    ),
                )
            )
        elif kind == "text":
            query = query.filter(
                CareMessage.media["content_type"].as_string().is_(None),
                ~CareMessage.id.in_(
                    db.query(CareAttachment.message_id).filter(
                        CareAttachment.message_id.is_not(None)
                    )
                ),
            )
        else:
            query = query.filter(
                CareMessage.id.in_(
                    db.query(CareAttachment.message_id).filter(
                        CareAttachment.kind == kind,
                        CareAttachment.status == "committed",
                    )
                )
            )
    rows = (
        query.order_by(CareMessage.created_at.desc(), CareMessage.id.desc())
        .limit(limit + 1)
        .all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    messages = enrich(db, list(reversed(rows)), u, pack)
    result = {
        "conversation": {
            "id": conv.id,
            "type": "direct",
            "sequence": conv.sequence,
            "status": conv.status,
        },
        "contact": {"id": target.id, "name": target.name, "role": target.role},
        "messages": messages,
        "next_before": rows[-1].id if more else None,
        "as_of": now(),
    }
    db.commit()
    return result


class Send(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    body: str = Field(default="", max_length=2000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=6)
    reply_to_id: str | None = Field(default=None, max_length=60)

    @field_validator("body")
    @classmethod
    def readable_text(cls, value):
        value = value.strip()
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("Enter a text message without control characters")
        return value

    @model_validator(mode="after")
    def has_content(self):
        if not self.body and not self.attachment_ids:
            raise ValueError("Enter text or attach a file")
        return self


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
    conv = conversation(db, pid, u, target)
    if conv.status != "active":
        raise HTTPException(409, "Conversation is archived")
    existing = (
        db.query(CareMessage)
        .filter_by(sender_id=u.id, command_id=body.command_id)
        .first()
    )
    if existing:
        linked = {
            r.id for r in db.query(CareAttachment).filter_by(message_id=existing.id)
        }
        if (
            existing.media
            or linked != set(body.attachment_ids)
            or existing.reply_to_id != body.reply_to_id
            or (
                existing.patient_id,
                existing.recipient_id,
                existing.body,
            )
            != (
                pid,
                target.id,
                body.body,
            )
        ):
            raise HTTPException(
                409, "Message command was already used for different content"
            )
        return enrich(db, [existing], u, pack)[0]
    if body.reply_to_id:
        quoted = (
            pair_query(db, pid, u.id, target.id)
            .filter(
                CareMessage.id == body.reply_to_id, CareMessage.withdrawn_at.is_(None)
            )
            .first()
        )
        if not quoted:
            raise HTTPException(
                404, "Reply source is not available in this conversation"
            )
    row = CareMessage(
        patient_id=pid,
        sender_id=u.id,
        recipient_id=target.id,
        body=body.body,
        command_id=body.command_id,
        conversation_id=conv.id,
        reply_to_id=body.reply_to_id,
    )
    try:
        db.add(row)
        db.flush()
        attach_to_message(db, u, conv, row, body.attachment_ids)
        emit(db, conv, row, "message.created")
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
    return enrich(db, [row], u, pack)[0]


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
        conv = conversation(db, pid, u, target)
        for row in changed:
            emit(db, conv, row, "receipt.opened")
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
