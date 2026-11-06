"""Authorized durable SSE, receipt acknowledgements, withdrawal and lookup."""

import asyncio
import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from .care_domain import conversation, emit, enrich
from .db import (
    Audit,
    CareConversation,
    CareEvent,
    CareMessage,
    CareReceipt,
    LoginSession,
    User,
    get_db,
    now,
)
from .messages import pack, pair_query, peer
from .security import authenticated, bind_actor, digest_token

router = APIRouter(
    prefix="/api/patients/{pid}/messages", tags=["care events and receipts"]
)


@router.get("/threads/{peer_id}/command/{command_id}")
def lookup(
    pid: str,
    peer_id: str,
    command_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    row = (
        pair_query(db, pid, u.id, target.id)
        .filter_by(sender_id=u.id, command_id=command_id)
        .first()
    )
    return {"message": enrich(db, [row], u, pack)[0] if row else None}


class ReceiptCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_ids: list[str] = Field(min_length=1, max_length=100)
    event: str = Field(pattern=r"^(delivered|playback_started|playback_completed)$")


@router.post("/threads/{peer_id}/receipts")
def receipt(
    pid: str,
    peer_id: str,
    body: ReceiptCommand,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    ids = set(body.message_ids)
    rows = (
        pair_query(db, pid, u.id, target.id)
        .filter(
            CareMessage.id.in_(ids),
            CareMessage.recipient_id == u.id,
            CareMessage.withdrawn_at.is_(None),
        )
        .all()
    )
    if len(rows) != len(ids):
        raise HTTPException(404, "Incoming messages are not available")
    if body.event.startswith("playback"):
        from .db import CareAttachment

        audio_ids = {
            r.message_id
            for r in db.query(CareAttachment).filter(
                CareAttachment.message_id.in_(ids),
                CareAttachment.kind.in_(["audio", "voice"]),
                CareAttachment.status == "committed",
            )
        }
        if any(not r.media and r.id not in audio_ids for r in rows):
            raise HTTPException(422, "Playback receipts require audio")
    conv = conversation(db, pid, u, target)
    changed = 0
    for row in rows:
        state = (
            db.query(CareReceipt)
            .filter_by(message_id=row.id, recipient_id=u.id)
            .first()
        )
        if not state:
            state = CareReceipt(message_id=row.id, recipient_id=u.id)
            db.add(state)
        column = body.event + "_at"
        if body.event == "playback_completed" and not state.playback_started_at:
            raise HTTPException(409, "Playback must start before it can finish")
        if not getattr(state, column):
            setattr(state, column, now())
            changed += 1
            emit(db, conv, row, "receipt." + body.event)
    if changed:
        db.add(
            Audit(
                patient_id=pid,
                actor=u.id,
                action="message.receipt",
                detail={
                    "message_ids": sorted(ids),
                    "event": body.event,
                    "evidence": "recipient client acknowledgement; not independent clinical evidence",
                },
            )
        )
    db.commit()
    return {"acknowledged": changed}


@router.post("/threads/{peer_id}/messages/{message_id}/withdraw")
def withdraw(
    pid: str,
    peer_id: str,
    message_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    row = (
        pair_query(db, pid, u.id, target.id)
        .filter(CareMessage.id == message_id, CareMessage.sender_id == u.id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Own message is not available")
    if row.withdrawn_at:
        return {"withdrawn_at": row.withdrawn_at}
    created = dt.datetime.fromisoformat(row.created_at)
    if dt.datetime.now(dt.timezone.utc) - created > dt.timedelta(hours=24):
        raise HTTPException(
            403, "Only your messages from the past 24 hours can be withdrawn"
        )
    row.withdrawn_at = now()
    conv = conversation(db, pid, u, target)
    emit(db, conv, row, "message.withdrawn")
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="message.withdrawn",
            detail={
                "message_id": row.id,
                "retention": "original evidence retained; future retrieval hidden",
            },
        )
    )
    db.commit()
    return {"withdrawn_at": row.withdrawn_at}


@router.get("/threads/{peer_id}/events")
def events(
    pid: str,
    peer_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    conv = conversation(db, pid, u, target)
    cid, actor_id = conv.id, u.id
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(422, "Invalid event cursor") from None
    token = digest_token(request.cookies.get("nt_session", ""))
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    db.commit()

    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            try:
                with factory() as current:
                    session = current.get(LoginSession, token)
                    if (
                        not session
                        or session.expires <= now()
                        or session.user_id != actor_id
                    ):
                        yield 'event: revoked\ndata: {"reason":"session_expired"}\n\n'
                        return
                    actor = current.get(User, actor_id)
                    bind_actor(current, actor_id)
                    peer(current, actor, pid, peer_id)
                    active = current.get(CareConversation, cid)
                    if cursor > active.sequence:
                        cursor = active.sequence
                        batch = [f'event: reset\ndata: {{"sequence":{cursor}}}\n\n']
                    else:
                        rows = (
                            current.query(CareEvent)
                            .filter(
                                CareEvent.conversation_id == cid,
                                CareEvent.sequence > cursor,
                            )
                            .order_by(CareEvent.sequence)
                            .limit(100)
                            .all()
                        )
                        batch = []
                        for row in rows:
                            batch.append(
                                f"id: {row.sequence}\nevent: care\ndata: "
                                + json.dumps(
                                    {
                                        "sequence": row.sequence,
                                        "type": row.event_type,
                                        "message_id": row.message_id,
                                        "conversation_id": cid,
                                    }
                                )
                                + "\n\n"
                            )
                            cursor = row.sequence
                    current.commit()
                if batch:
                    for item in batch:
                        yield item
                else:
                    yield ": heartbeat\n\n"
            except HTTPException:
                yield 'event: revoked\ndata: {"reason":"access_changed"}\n\n'
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
