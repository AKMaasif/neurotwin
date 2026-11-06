"""Idempotent private-object maintenance. Committed evidence is never auto-deleted."""

import datetime as dt
import hashlib
import uuid

from .care_domain import conversation_id
from .db import (
    Audit,
    CareAttachment,
    CareAudio,
    CareConversation,
    CareMessage,
    Session,
    now,
)
from .media_processor import waveform
from .media_store import delete_object, object_path, write_object


def cleanup(db):
    rows = (
        db.query(CareAttachment)
        .filter(
            CareAttachment.message_id.is_(None),
            CareAttachment.expires_at < now(),
            CareAttachment.status != "expired",
        )
        .with_for_update(skip_locked=True)
        .limit(100)
        .all()
    )
    for row in rows:
        row.status = "expired"
        delete_object(row.original_key)
        delete_object(row.object_key)
        if row.object_key:
            delete_object(row.object_key + ".thumb")
        conv = db.get(CareConversation, row.conversation_id)
        db.add(
            Audit(
                patient_id=conv.patient_id,
                actor="media_cleanup",
                action="attachment.expired",
                detail={"attachment_id": row.id},
            )
        )
    db.commit()
    # Remove only old unreferenced objects under the configured private root.
    root = object_path("maintenance-anchor").parent
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - 86400
    referenced = set()
    for row in db.query(CareAttachment):
        if row.status == "expired":
            continue
        referenced.add(row.original_key)
        if row.object_key:
            referenced.update([row.object_key, row.object_key + ".thumb"])
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                key = path.relative_to(root).as_posix()
                if key not in referenced:
                    delete_object(key)
    return len(rows)


def migrate_legacy(db):
    import io
    import wave

    count = 0
    for legacy in db.query(CareAudio).filter(CareAudio.data != b"").limit(25):
        message = db.get(CareMessage, legacy.message_id)
        cid = message.conversation_id or conversation_id(
            message.patient_id, message.sender_id, message.recipient_id
        )
        conv = db.get(CareConversation, cid)
        if not conv:
            a, b = sorted([message.sender_id, message.recipient_id])
            conv = CareConversation(
                id=cid,
                patient_id=message.patient_id,
                first_user=a,
                second_user=b,
                created_by=message.sender_id,
            )
            db.add(conv)
            db.flush()
        message.conversation_id = cid
        existing = (
            db.query(CareAttachment)
            .filter_by(message_id=message.id, kind="voice")
            .first()
        )
        if not existing:
            aid = str(uuid.uuid5(uuid.NAMESPACE_URL, "legacy-voice:" + message.id))
            key = f"{cid}/{aid}/ready-legacy"
            data = legacy.data
            sha = hashlib.sha256(data).hexdigest()
            write_object(key, data)
            if hashlib.sha256(object_path(key).read_bytes()).hexdigest() != sha:
                raise RuntimeError("Legacy audio copy verification failed")
            with wave.open(io.BytesIO(data)) as audio:
                pcm = audio.readframes(audio.getnframes())
                duration = round(1000 * audio.getnframes() / audio.getframerate())
            detail = {
                "content_type": "audio/wav",
                "bytes": len(data),
                "sha256": sha,
                "duration_ms": duration,
                "waveform": waveform(pcm),
                "clean_filename": "voice-note.wav",
                "scan_status": "legacy_pcm_validated",
            }
            existing = CareAttachment(
                id=aid,
                conversation_id=cid,
                uploader_id=message.sender_id,
                client_attachment_id=aid,
                client_message_id=message.command_id,
                message_id=message.id,
                filename="voice-note.wav",
                claimed_type="audio/wav",
                kind="voice",
                expected_size=len(data),
                offset=len(data),
                expected_sha256=sha,
                status="committed",
                original_key=key,
                object_key=key,
                detail=detail,
                expires_at=now(),
            )
            db.add(existing)
            message.media = message.media | {
                "waveform": detail["waveform"],
                "attachment_id": aid,
            }
        legacy.data = b""
        db.add(
            Audit(
                patient_id=message.patient_id,
                actor="media_migration",
                action="message.voice_externalized",
                detail={"message_id": message.id, "attachment_id": existing.id},
            )
        )
        db.commit()
        count += 1
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["cleanup", "migrate-legacy"])
    args = parser.parse_args()
    with Session() as db:
        result = migrate_legacy(db) if args.action == "migrate-legacy" else cleanup(db)
    print({"action": args.action, "processed": result})
