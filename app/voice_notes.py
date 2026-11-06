"""Locally stored, bounded PCM voice notes for authorized direct conversations."""

import hashlib
import io
import wave

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Audit, CareAudio, CareMessage, User, get_db
from .messages import Send, pack, peer
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/messages", tags=["voice notes"])
MAX_BYTES = 2 * 1024 * 1024


def pcm_clip(data):
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            rate, frames = source.getframerate(), source.getnframes()
            if (
                source.getnchannels() != 1
                or source.getsampwidth() != 2
                or rate not in (16000, 24000)
                or source.getcomptype() != "NONE"
                or not 0 < frames <= rate * 30
            ):
                raise ValueError("Unsupported audio")
            pcm = source.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError("Truncated audio")
        if not any(pcm):
            raise HTTPException(
                422, "No sound detected. Record again or send a text message."
            )
        # Re-encode only validated PCM; uploaded metadata/trailing chunks are discarded.
        out = io.BytesIO()
        with wave.open(out, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(rate)
            target.writeframes(pcm)
        return out.getvalue(), round(1000 * frames / rate)
    except (wave.Error, EOFError, ValueError):
        raise HTTPException(
            415, "Use a mono 16-bit PCM WAV at 16 or 24 kHz, up to 30 seconds"
        ) from None


def synthetic(db, u, pid):
    if not authorize(db, u, pid, "messages").synthetic:
        raise HTTPException(
            403, "Voice notes require a synthetic development workspace"
        )


@router.post("/threads/{peer_id}/voice")
async def upload(
    pid: str,
    peer_id: str,
    audio: UploadFile | None = File(default=None),
    command_id: str = Form(min_length=16, max_length=100),
    caption: str = Form(default="", max_length=2000),
    upload_id: str | None = Form(default=None, max_length=60),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    import uuid

    from .care_domain import attach_to_message, conversation, emit
    from .db import CareAttachment
    from .media_store import write_object
    from .media_uploads import Upload, complete, own, reserve

    target = peer(db, u, pid, peer_id)
    synthetic(db, u, pid)
    try:
        command = Send(command_id=command_id, body=caption.strip() or "Voice note")
    except ValidationError:
        raise HTTPException(
            422, "Use a valid message ID and plain text caption"
        ) from None
    source_sha = None
    if audio is not None:
        if audio.content_type != "audio/wav":
            raise HTTPException(415, "Use audio/wav for voice notes")
        data = await audio.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Voice note exceeds 2 MB")
        data, duration = pcm_clip(data)
        source_sha = hashlib.sha256(data).hexdigest()
    elif not upload_id:
        raise HTTPException(
            422, "Record a voice note or supply a verified voice upload"
        )
    existing = (
        db.query(CareMessage).filter_by(sender_id=u.id, command_id=command_id).first()
    )
    if existing:
        attachment = db.query(CareAttachment).filter_by(message_id=existing.id).first()
        same_source = (
            (
                existing.media.get("input_sha256", existing.media.get("sha256"))
                == source_sha
            )
            if audio is not None
            else attachment and attachment.id == upload_id
        )
        if (
            not existing.media
            or (existing.patient_id, existing.recipient_id, existing.body)
            != (pid, target.id, command.body)
            or not same_source
        ):
            raise HTTPException(
                409, "Message command was already used for different content"
            )
        return pack(existing, u)
    if audio is not None:
        body = Upload(
            client_message_id=command_id,
            client_attachment_id=str(
                uuid.uuid5(uuid.NAMESPACE_URL, "voice:" + command_id)
            ),
            filename="voice-note.wav",
            content_type="audio/wav",
            size=len(data),
            sha256=source_sha,
            kind="voice",
        )
        attachment = reserve(db, u, pid, target, body)
        if attachment.status == "uploading" and attachment.offset == 0:
            write_object(attachment.original_key, data)
            attachment.offset = len(data)
        upload_id = attachment.id
        db.commit()
        await complete(pid, upload_id, u, db)
    db.expire_all()
    target = peer(db, u, pid, peer_id)
    synthetic(db, u, pid)
    attachment = own(db, u, pid, upload_id)
    if attachment.kind != "voice" or attachment.client_message_id != command_id:
        raise HTTPException(409, "Voice upload does not match this send")
    if attachment.status != "ready":
        raise HTTPException(
            409 if attachment.status in {"verifying", "uploading"} else 415,
            "Voice note is not ready or failed file validation",
        )
    conv = conversation(db, pid, u, target)
    metadata = {
        k: v
        for k, v in attachment.detail.items()
        if k in {"duration_ms", "waveform", "content_type", "bytes", "sha256"}
    }
    metadata.update(
        input_sha256=source_sha or attachment.expected_sha256,
        attachment_id=attachment.id,
    )
    message = CareMessage(
        patient_id=pid,
        sender_id=u.id,
        recipient_id=target.id,
        command_id=command_id,
        body=command.body,
        media=metadata,
        conversation_id=conv.id,
    )
    try:
        db.add(message)
        db.flush()
        attach_to_message(db, u, conv, message, [attachment.id])
        # Keep a compatibility marker, not another binary copy. Old nonempty rows remain readable.
        db.add(CareAudio(message_id=message.id, data=b""))
        emit(db, conv, message, "message.created")
        db.add(
            Audit(
                patient_id=pid,
                actor=u.id,
                action="message.voice_saved",
                detail={
                    "message_id": message.id,
                    "recipient_id": target.id,
                    "duration_ms": metadata["duration_ms"],
                },
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Message changed concurrently; reconcile this command ID"
        ) from None
    return pack(message, u)


@router.get("/voice/{message_id}")
def audio(
    pid: str,
    message_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    synthetic(db, u, pid)
    message = db.get(CareMessage, message_id)
    if (
        not message
        or message.patient_id != pid
        or u.id not in (message.sender_id, message.recipient_id)
        or not message.media
        or message.withdrawn_at
    ):
        raise HTTPException(404, "Voice note is not available")
    peer_id = message.recipient_id if u.id == message.sender_id else message.sender_id
    peer(db, u, pid, peer_id)
    asset = db.get(CareAudio, message.id)
    if not asset:
        raise HTTPException(404, "Voice note is not available")
    from fastapi.responses import FileResponse

    from .db import CareAttachment
    from .media_store import object_path

    attachment = (
        db.query(CareAttachment)
        .filter_by(message_id=message.id, status="committed")
        .first()
    )
    private_path = (
        object_path(attachment.object_key)
        if attachment and attachment.object_key
        else None
    )
    if not asset.data and (not private_path or not private_path.is_file()):
        raise HTTPException(404, "Voice note is not available")
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="message.voice_accessed",
            detail={
                "message_id": message.id,
                "evidence": "audio fetched; not an opening acknowledgement",
            },
        )
    )
    db.commit()
    if private_path and private_path.is_file():
        return FileResponse(
            private_path,
            media_type="audio/wav",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": 'inline; filename="voice-note.wav"',
            },
        )
    return Response(
        asset.data,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="voice-note.wav"',
        },
    )
