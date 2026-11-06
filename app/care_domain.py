"""Canonical direct conversations and durable, minimal messaging events."""

import uuid
from collections import defaultdict

from fastapi import HTTPException

from .db import (
    CareAttachment,
    CareConversation,
    CareEvent,
    CareMessage,
    CareParticipant,
    CareReceipt,
    Grant,
    now,
)


def conversation_id(pid, first, second):
    a, b = sorted((first, second))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"neurotwin:care:{pid}:{a}:{b}"))


def conversation(db, pid, actor, target):
    cid = conversation_id(pid, actor.id, target.id)
    row = db.get(CareConversation, cid)
    if not row:
        a, b = sorted((actor.id, target.id))
        row = CareConversation(
            id=cid, patient_id=pid, first_user=a, second_user=b, created_by=actor.id
        )
        db.add(row)
        db.flush()
    members = {
        member.user_id
        for member in db.query(CareParticipant).filter_by(conversation_id=cid)
    }
    for user in (actor, target):
        if user.id not in members:
            grant = db.query(Grant).filter_by(patient_id=pid, user_id=user.id).one()
            db.add(
                CareParticipant(conversation_id=cid, user_id=user.id, grant_id=grant.id)
            )
    # Backward compatibility for pre-conversation records and old fixtures.
    db.query(CareMessage).filter(
        CareMessage.patient_id == pid,
        CareMessage.conversation_id.is_(None),
        CareMessage.sender_id.in_([actor.id, target.id]),
        CareMessage.recipient_id.in_([actor.id, target.id]),
    ).update({CareMessage.conversation_id: cid}, synchronize_session=False)
    return row


def emit(db, conv, message, event_type):
    conv.sequence += 1
    db.add(
        CareEvent(
            conversation_id=conv.id,
            sequence=conv.sequence,
            message_id=message.id,
            event_type=event_type,
        )
    )


def ready_attachment(row):
    return {
        "id": row.id,
        "kind": row.kind,
        "filename": row.filename,
        "status": row.status,
        "content_type": row.detail.get("content_type"),
        "size": row.detail.get("bytes"),
        "sha256": row.detail.get("sha256"),
        "duration_ms": row.detail.get("duration_ms"),
        "width": row.detail.get("width"),
        "height": row.detail.get("height"),
        "pages": row.detail.get("pages"),
        "waveform": row.detail.get("waveform"),
        "scan_status": row.detail.get("scan_status"),
        "reconstruction": row.detail.get("reconstruction"),
        "url": f"/api/patients/{{pid}}/messages/attachments/{row.id}/content",
        "thumbnail": bool(row.detail.get("thumbnail_key")),
    }


def enrich(db, rows, actor, base_pack):
    ids = [r.id for r in rows]
    grouped = defaultdict(list)
    for item in (
        db.query(CareAttachment)
        .filter(
            CareAttachment.message_id.in_(ids), CareAttachment.status == "committed"
        )
        .order_by(CareAttachment.created_at, CareAttachment.id)
    ):
        grouped[item.message_id].append(item)
    receipts = {
        r.message_id: r
        for r in db.query(CareReceipt).filter(CareReceipt.message_id.in_(ids))
    }
    reply_ids = {r.reply_to_id for r in rows if r.reply_to_id}
    quoted = {
        r.id: r for r in db.query(CareMessage).filter(CareMessage.id.in_(reply_ids))
    }
    results = []
    for row in rows:
        result = base_pack(row, actor)
        files = []
        if not row.withdrawn_at:
            for item in grouped[row.id]:
                metadata = ready_attachment(item)
                metadata["url"] = metadata["url"].replace("{pid}", row.patient_id)
                files.append(metadata)
        receipt = receipts.get(row.id)
        quote = quoted.get(row.reply_to_id)
        if quote and quote.conversation_id != row.conversation_id:
            quote = None
        result.update(
            conversation_id=row.conversation_id,
            attachments=files,
            withdrawn_at=row.withdrawn_at,
            reply_to={
                "id": quote.id,
                "body": "Message withdrawn" if quote.withdrawn_at else quote.body[:180],
                "sender_id": quote.sender_id,
            }
            if quote
            else None,
            receipt={
                "delivered_at": receipt.delivered_at if receipt else None,
                "opened_at": row.opened_at,
                "playback_started_at": receipt.playback_started_at if receipt else None,
                "playback_completed_at": receipt.playback_completed_at
                if receipt
                else None,
            },
        )
        if row.withdrawn_at:
            result.update(body="Message withdrawn", voice=None, message_type="system")
        elif files and not row.media:
            result["message_type"] = (
                files[0]["kind"] if len(files) == 1 else "attachments"
            )
        results.append(result)
    return results


def attach_to_message(db, actor, conv, message, attachment_ids):
    if len(set(attachment_ids)) != len(attachment_ids):
        raise HTTPException(422, "Duplicate attachment in message")
    items = db.query(CareAttachment).filter(CareAttachment.id.in_(attachment_ids)).all()
    if len(items) != len(attachment_ids):
        raise HTTPException(404, "Attachment is not available")
    from .config import settings
    from .media_store import object_path

    total = 0
    for item in items:
        if (
            item.uploader_id != actor.id
            or item.conversation_id != conv.id
            or item.client_message_id != message.command_id
        ):
            raise HTTPException(
                403, "Attachment does not belong to this send operation"
            )
        if (
            item.status != "ready"
            or item.message_id
            or item.expires_at < now()
            or not item.object_key
            or not object_path(item.object_key).is_file()
        ):
            raise HTTPException(
                409, "Attachment is not ready; resume or verify the upload"
            )
        import hashlib

        with object_path(item.object_key).open("rb") as stored:
            if hashlib.file_digest(stored, "sha256").hexdigest() != item.detail.get(
                "sha256"
            ):
                raise HTTPException(409, "Stored attachment changed; upload a new copy")
        total += max(item.expected_size, item.detail.get("bytes", 0))
    if total > settings.media_message_mb * 1024 * 1024:
        raise HTTPException(
            413, "Combined attachments exceed this application's message limit"
        )
    for item in items:
        item.message_id = message.id
        item.status = "committed"
