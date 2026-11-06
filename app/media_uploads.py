"""Authenticated resumable uploads, private validation and authorized retrieval."""

import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .care_domain import conversation
from .config import ROOT, settings
from .db import (
    Audit,
    CareAttachment,
    CareConversation,
    CareMessage,
    User,
    get_db,
    now,
    uid,
)
from .media_store import delete_object, object_path
from .messages import peer
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/messages", tags=["private attachments"])
CHUNK = 1024 * 1024
PROCESSING = asyncio.Semaphore(2)
TYPES = {
    ".jpg": ("image", ["image/jpeg"]),
    ".jpeg": ("image", ["image/jpeg"]),
    ".png": ("image", ["image/png"]),
    ".webp": ("image", ["image/webp"]),
    ".mp4": ("video", ["video/mp4"]),
    ".webm": ("video", ["video/webm", "audio/webm"]),
    ".wav": ("audio", ["audio/wav", "audio/x-wav"]),
    ".mp3": ("audio", ["audio/mpeg"]),
    ".m4a": ("audio", ["audio/mp4", "audio/x-m4a"]),
    ".ogg": ("audio", ["audio/ogg"]),
    ".pdf": ("document", ["application/pdf"]),
    ".docx": (
        "document",
        ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    ),
    ".xlsx": (
        "document",
        ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    ),
    ".txt": ("document", ["text/plain"]),
    ".csv": ("document", ["text/csv", "application/vnd.ms-excel", "text/plain"]),
}


def filename(value):
    name = unicodedata.normalize("NFKC", value.replace("\\", "/").split("/")[-1])
    name = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "_", name).strip(" .")[:180]
    if not name:
        raise HTTPException(422, "Choose a named file")
    return name


def limit_for(kind):
    return (
        {
            "image": settings.media_image_mb,
            "video": settings.media_video_mb,
            "audio": settings.media_audio_mb,
            "voice": 2,
            "document": settings.media_document_mb,
        }[kind]
        * 1024
        * 1024
    )


def policy(name, mime, kind=None):
    extension = Path(name).suffix.lower()
    if extension not in TYPES:
        raise HTTPException(415, "This file type is not allowed")
    category, mimes = TYPES[extension]
    if extension == ".webm" and mime.startswith("audio/"):
        category = "audio"
    if kind == "voice" and extension in {".wav", ".webm", ".ogg", ".m4a"}:
        category = "voice"
    if kind and kind != category:
        raise HTTPException(415, "File category does not match its extension")
    if (
        mime.split(";", 1)[0].strip().lower() not in mimes
        and mime != "application/octet-stream"
    ):
        raise HTTPException(
            415, "Declared file type does not match the allowed extension"
        )
    return category, extension


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_message_id: str = Field(
        min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    )
    client_attachment_id: str = Field(
        min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    )
    filename: str = Field(min_length=1, max_length=250)
    content_type: str = Field(max_length=150)
    size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: str | None = Field(default=None, max_length=20)


def pack(row):
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "client_message_id": row.client_message_id,
        "client_attachment_id": row.client_attachment_id,
        "filename": row.filename,
        "kind": row.kind,
        "expected_size": row.expected_size,
        "sha256": row.expected_sha256,
        "offset": row.offset,
        "status": row.status,
        "error": row.error,
        "detail": {
            k: v
            for k, v in row.detail.items()
            if k
            in {
                "content_type",
                "duration_ms",
                "width",
                "height",
                "pages",
                "bytes",
                "scan_status",
                "reconstruction",
                "waveform",
            }
        },
        "expires_at": row.expires_at,
        "message_id": row.message_id,
        "chunk_size": CHUNK,
    }


def check_synthetic(db, u, pid):
    if not authorize(db, u, pid, "messages").synthetic:
        raise HTTPException(
            403, "Attachments require a synthetic development workspace"
        )


def own(db, u, pid, upload_id):
    check_synthetic(db, u, pid)
    row = db.get(CareAttachment, upload_id)
    if not row or row.uploader_id != u.id:
        raise HTTPException(404, "Upload is not available")
    conv = db.get(CareConversation, row.conversation_id)
    if not conv or conv.patient_id != pid:
        raise HTTPException(404, "Upload is not available")
    target = conv.second_user if conv.first_user == u.id else conv.first_user
    peer(db, u, pid, target)
    if row.expires_at < now() and row.status != "committed":
        raise HTTPException(410, "Upload expired; select the file again for a new send")
    return row


def reserve(db, u, pid, target, body):
    check_synthetic(db, u, pid)
    conv = conversation(db, pid, u, target)
    if conv.status != "active":
        raise HTTPException(409, "Conversation is archived")
    name = filename(body.filename)
    kind, _ = policy(name, body.content_type, body.kind)
    if body.size > limit_for(kind):
        raise HTTPException(413, "File exceeds the configured limit for its type")
    previous = (
        db.query(CareAttachment)
        .filter_by(uploader_id=u.id, client_attachment_id=body.client_attachment_id)
        .first()
    )
    if previous:
        if (
            previous.conversation_id,
            previous.client_message_id,
            previous.filename,
            previous.expected_size,
            previous.expected_sha256,
            previous.claimed_type,
            previous.kind,
        ) != (
            conv.id,
            body.client_message_id,
            name,
            body.size,
            body.sha256,
            body.content_type,
            kind,
        ):
            raise HTTPException(
                409, "Attachment ID was already used for different content"
            )
        return previous
    db.query(User).filter_by(id=u.id).with_for_update().one()
    day = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()
    if (
        db.query(CareAttachment)
        .filter(CareAttachment.uploader_id == u.id, CareAttachment.created_at >= day)
        .count()
        >= settings.media_uploads_per_day
    ):
        raise HTTPException(
            429, "Daily attachment limit reached", headers={"Retry-After": "3600"}
        )
    total = (
        db.query(func.coalesce(func.sum(CareAttachment.expected_size), 0))
        .filter(
            CareAttachment.uploader_id == u.id,
            ~CareAttachment.status.in_(["cancelled", "expired", "rejected"]),
        )
        .scalar()
    )
    if total + body.size > settings.media_user_quota_mb * 1024 * 1024:
        raise HTTPException(413, "Private media quota reached")
    row = CareAttachment(
        id=uid(),
        conversation_id=conv.id,
        uploader_id=u.id,
        client_attachment_id=body.client_attachment_id,
        client_message_id=body.client_message_id,
        filename=name,
        claimed_type=body.content_type,
        kind=kind,
        expected_size=body.size,
        expected_sha256=body.sha256,
        original_key="pending",
        expires_at=(
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)
        ).isoformat(),
    )
    row.original_key = f"{conv.id}/{row.id}/original"
    db.add(row)
    db.flush()
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="attachment.reserved",
            detail={"attachment_id": row.id},
        )
    )
    return row


@router.get("/media-policy")
def media_policy(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    check_synthetic(db, u, pid)
    return {
        "extensions": list(TYPES),
        "limits": {
            k: limit_for(k) for k in ["image", "video", "audio", "document", "voice"]
        },
        "total_bytes": settings.media_message_mb * 1024 * 1024,
        "max_files": 6,
        "chunk_bytes": CHUNK,
        "scanner_configured": bool(settings.media_scan_executable),
        "development_unscanned": settings.app_env == "development"
        and settings.media_allow_unscanned_development,
    }


@router.post("/threads/{peer_id}/uploads")
def create(
    pid: str,
    peer_id: str,
    body: Upload,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    row = reserve(db, u, pid, target, body)
    db.commit()
    return pack(row)


@router.get("/uploads/{upload_id}")
def status(
    pid: str,
    upload_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    return pack(own(db, u, pid, upload_id))


@router.get("/threads/{peer_id}/uploads")
def recover(
    pid: str,
    peer_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    target = peer(db, u, pid, peer_id)
    conv = conversation(db, pid, u, target)
    rows = (
        db.query(CareAttachment)
        .filter(
            CareAttachment.conversation_id == conv.id,
            CareAttachment.uploader_id == u.id,
            CareAttachment.message_id.is_(None),
            CareAttachment.expires_at > now(),
            ~CareAttachment.status.in_(["cancelled", "rejected", "expired"]),
        )
        .order_by(CareAttachment.created_at.desc())
        .limit(30)
        .all()
    )
    result = [pack(r) for r in rows]
    db.commit()
    return result


@router.patch("/uploads/{upload_id}")
async def chunk(
    pid: str,
    upload_id: str,
    request: Request,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row = own(db, u, pid, upload_id)
    if row.status != "uploading":
        raise HTTPException(409, "Upload is not accepting bytes")
    try:
        offset = int(request.headers.get("upload-offset", "-1"))
    except ValueError:
        raise HTTPException(422, "Use a valid Upload-Offset") from None
    if offset != row.offset:
        raise HTTPException(
            409,
            "Offset changed; query upload status",
            headers={"Upload-Offset": str(row.offset)},
        )
    data = bytearray()
    async for block in request.stream():
        data.extend(block)
        if len(data) > CHUNK:
            raise HTTPException(413, "Chunk exceeds 1 MB")
    if not data or row.offset + len(data) > row.expected_size:
        raise HTTPException(422, "Chunk exceeds the reserved size or is empty")
    path = object_path(row.original_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("r+b" if path.exists() else "w+b") as stream:
        stream.seek(0, 2)
        if stream.tell() < row.offset:
            raise HTTPException(
                409, "Stored bytes are incomplete; cancel and start a new upload"
            )
        stream.truncate(row.offset)
        stream.seek(row.offset)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    row.offset += len(data)
    db.commit()
    return pack(row)


def process_file(row):
    path = object_path(row.original_key)
    if (
        not path.is_file()
        or path.stat().st_size != row.expected_size
        or hashlib.sha256(path.read_bytes()).hexdigest() != row.expected_sha256
    ):
        return {"ok": False, "error": "checksum_or_size_mismatch"}
    scan = "not_configured_development"
    if settings.media_scan_executable:
        try:
            result = subprocess.run(
                [settings.media_scan_executable, "--no-summary", str(path)],
                capture_output=True,
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                return {
                    "ok": False,
                    "error": "malware_detected"
                    if result.returncode == 1
                    else "scanner_unavailable",
                    "quarantine": True,
                }
            scan = "antivirus_passed"
        except (OSError, subprocess.TimeoutExpired):
            return {"ok": False, "error": "scanner_unavailable", "quarantine": True}
    elif not (
        settings.app_env == "development" and settings.media_allow_unscanned_development
    ):
        return {"ok": False, "error": "scanner_required", "quarantine": True}
    key = f"{row.conversation_id}/{row.id}/ready-{row.detail.get('token', 'legacy')}"
    out = object_path(key)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.media_processor",
                str(path),
                str(out),
                row.kind,
                Path(row.filename).suffix.lower(),
            ],
            cwd=ROOT,
            capture_output=True,
            timeout=settings.media_process_timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        result = json.loads(run.stdout.decode("utf-8"))
        if run.returncode or not result.get("ok"):
            return {"ok": False, "error": "unsafe_or_unsupported_media"}
        detail = result["detail"]
        if out.stat().st_size > limit_for(row.kind):
            return {"ok": False, "error": "processed_file_exceeds_limit"}
        detail.update(
            scan_status=scan,
            original_sha256=row.expected_sha256,
            clean_filename=Path(row.filename).stem + detail["extension"],
        )
        if detail.pop("thumbnail", False):
            detail["thumbnail_key"] = key + ".thumb"
        return {"ok": True, "detail": detail, "key": key}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"ok": False, "error": "processing_failed"}


@router.post("/uploads/{upload_id}/complete")
async def complete(
    pid: str,
    upload_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
    retry_scan: bool = False,
):
    row = own(db, u, pid, upload_id)
    if (
        retry_scan
        and row.status == "quarantined"
        and row.error in {"scanner_required", "scanner_unavailable"}
        and settings.media_scan_executable
    ):
        row.status = "uploading"
        row.error = None
        row.detail = {}
        db.add(
            Audit(
                patient_id=pid,
                actor=u.id,
                action="attachment.scan_retried",
                detail={"attachment_id": row.id},
            )
        )
    if row.status in {"ready", "committed", "rejected", "quarantined"}:
        return pack(row)
    db.commit()  # Never hold a patient/connection lock while waiting for a worker slot.
    async with PROCESSING:
        db.expire_all()
        return await _complete_one(pid, upload_id, u, db)


async def _complete_one(
    pid: str,
    upload_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row = own(db, u, pid, upload_id)
    if row.status in {"ready", "committed", "rejected", "quarantined"}:
        return pack(row)
    if row.status == "verifying" and row.detail.get("lease_until", "") > now():
        return pack(row)
    if row.status not in {"uploading", "verifying"} or row.offset != row.expected_size:
        raise HTTPException(409, "Upload is incomplete or cancelled")
    token = uid()
    row.status = "verifying"
    row.detail = {
        "token": token,
        "lease_until": (
            dt.datetime.now(dt.timezone.utc)
            + dt.timedelta(seconds=settings.media_process_timeout_seconds + 45)
        ).isoformat(),
    }
    processing_key = f"{row.conversation_id}/{row.id}/ready-{token}"
    db.commit()
    result = await asyncio.to_thread(process_file, row)
    db.expire_all()
    try:
        row = own(db, u, pid, upload_id)
    except HTTPException:
        delete_object(processing_key)
        delete_object(processing_key + ".thumb")
        raise
    if row.status != "verifying" or row.detail.get("token") != token:
        delete_object(processing_key)
        delete_object(processing_key + ".thumb")
        raise HTTPException(409, "Upload changed while processing")
    if result["ok"]:
        row.status = "ready"
        row.object_key = result["key"]
        row.detail = result["detail"]
        row.error = None
    else:
        row.status = "quarantined" if result.get("quarantine") else "rejected"
        row.error = result["error"]
        delete_object(processing_key)
        delete_object(processing_key + ".thumb")
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="attachment.verified" if result["ok"] else "attachment.blocked",
            detail={"attachment_id": row.id, "status": row.status, "error": row.error},
        )
    )
    db.commit()
    return pack(row)


@router.delete("/uploads/{upload_id}")
def cancel(
    pid: str,
    upload_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row = own(db, u, pid, upload_id)
    if row.message_id or row.status == "committed":
        raise HTTPException(409, "Message was already saved; use withdrawal instead")
    row.status = "cancelled"
    db.commit()
    delete_object(row.original_key)
    delete_object(row.object_key)
    if row.object_key:
        delete_object(row.object_key + ".thumb")
    return pack(row)


@router.get("/uploads/{upload_id}/preview")
def preview_upload(
    pid: str,
    upload_id: str,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    """Only the uploader can review a fully verified, uncommitted draft."""
    row = own(db, u, pid, upload_id)
    if (
        row.status != "ready"
        or not row.object_key
        or not object_path(row.object_key).is_file()
    ):
        raise HTTPException(404, "Verified draft is unavailable")
    path = object_path(row.object_key)
    mime = row.detail["content_type"]
    db.commit()
    return FileResponse(
        path,
        media_type=mime,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.get("/attachments/{attachment_id}/content")
def content(
    pid: str,
    attachment_id: str,
    download: bool = False,
    thumbnail: bool = False,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    check_synthetic(db, u, pid)
    row = db.get(CareAttachment, attachment_id)
    message = db.get(CareMessage, row.message_id) if row and row.message_id else None
    if (
        not message
        or message.patient_id != pid
        or u.id not in {message.sender_id, message.recipient_id}
        or message.withdrawn_at
        or row.status != "committed"
    ):
        raise HTTPException(404, "Attachment is not available")
    peer(
        db,
        u,
        pid,
        message.recipient_id if message.sender_id == u.id else message.sender_id,
    )
    key = row.detail.get("thumbnail_key") if thumbnail else row.object_key
    if not key or not object_path(key).is_file():
        raise HTTPException(404, "Attachment is not available")
    mime = "image/jpeg" if thumbnail else row.detail["content_type"]
    name = row.detail.get("clean_filename", row.filename)
    disposition = (
        "attachment"
        if download or (row.kind == "document" and not thumbnail)
        else "inline"
    )
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="attachment.downloaded" if download else "attachment.accessed",
            detail={
                "attachment_id": row.id,
                "variant": "thumbnail" if thumbnail else "ready",
            },
        )
    )
    db.commit()
    return FileResponse(
        object_path(key),
        media_type=mime,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(name, safe='')}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
