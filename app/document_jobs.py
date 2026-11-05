"""Durable extraction queue. Run separately: uv run python -m app.document_jobs."""

import base64
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time

from sqlalchemy import delete, or_, select

from .config import ROOT, settings
from .db import (
    Audit,
    DocumentAsset,
    DocumentChunk,
    DocumentJob,
    DocumentUnit,
    Record,
    Session,
    SourceFile,
    User,
    now,
)
from .document_retrieval import split_unit, terms
from .security import authorize


def clear_derived(db, rid):
    for cls in [DocumentChunk, DocumentAsset, DocumentUnit]:
        db.execute(delete(cls).where(cls.document_id == rid))


def backfill_legacy(factory=Session):
    """Index already-preserved text without rerunning AI or changing verified facts."""
    with factory() as db:
        records = (
            db.query(Record)
            .filter_by(kind="document")
            .filter(Record.status != "deleted")
            .with_for_update()
            .all()
        )
        count = 0
        for r in records:
            if r.payload.get("generation"):
                continue
            original = db.get(SourceFile, r.id)
            pages = r.payload.get("pages", [])
            items = [
                (p["text"], {"page": p["number"]}) for p in pages if p["text"]
            ] or (
                [(r.payload["text"], {"paragraph": 1})] if r.payload.get("text") else []
            )
            for n, (text, source) in enumerate(items):
                u = DocumentUnit(
                    document_id=r.id,
                    generation=1,
                    ordinal=n,
                    kind="paragraph",
                    text=text,
                    source=source,
                    detail={"method": "preserved_legacy_text"},
                )
                db.add(u)
                db.flush()
                for part in split_unit(text):
                    db.add(
                        DocumentChunk(
                            document_id=r.id,
                            generation=1,
                            unit_id=u.id,
                            kind="paragraph",
                            text=part,
                            source=source,
                            terms=dict(terms(part)),
                        )
                    )
            r.payload = r.payload | {
                "generation": 1,
                "format": "pdf" if original else "txt",
                "processing_status": "partial"
                if r.status == "ocr_required"
                else "processed",
                "warnings": [
                    "Legacy PDF contains pages without readable text. Reprocess to apply OCR."
                ]
                if r.status == "ocr_required"
                else [],
                "unit_count": len(items),
                "asset_count": 0,
            }
            count += 1
        db.commit()
        return count


def invalidate(db, r):
    for kind in ["plan", "draft"]:
        for item in (
            db.query(Record)
            .filter_by(patient_id=r.patient_id, kind=kind)
            .with_for_update()
        ):
            if r.id in item.payload.get("source_versions", {}):
                item.payload = item.payload | {"source_review_required": True}
                item.version += 1
                if kind == "draft" or item.status == "draft":
                    item.status = "source_changed"


def queue(db, r, actor):
    generation = r.payload.get("generation", 0) + 1
    invalidate(db, r)
    clear_derived(db, r.id)
    for job in db.query(DocumentJob).filter_by(document_id=r.id):
        if job.status in ["queued", "processing"]:
            job.status = "cancelled"
    r.version += 1
    r.status = "awaiting_extraction"
    r.payload = r.payload | {
        "generation": generation,
        "processing_status": "queued",
        "text": "",
        "candidates": [],
        "warnings": [],
        "pages": [],
        "stage": "waiting",
        "visual_description_count": 0,
        "embedded_chunks": 0,
        "embedding_model": None,
        "revisions": r.payload.get("revisions", [])
        + (
            [
                {
                    "event": "reprocessed",
                    "at": now(),
                    "actor": actor,
                    "prior_generation": generation - 1,
                    "prior_candidates": r.payload.get("candidates", []),
                }
            ]
            if generation > 1
            else []
        ),
    }
    job = DocumentJob(
        document_id=r.id,
        generation=generation,
        requested_by=actor,
        history=[{"stage": "queued", "at": now()}],
    )
    db.add(job)
    return job


def parse_subprocess(raw, filename):
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(s in k.upper() for s in ["KEY", "TOKEN", "PASSWORD", "DATABASE_URL"])
    }
    env.update({"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"})
    if settings.document_soffice:
        env["DOCUMENT_SOFFICE"] = settings.document_soffice
    result = subprocess.run(
        [sys.executable, "-m", "app.document_parser", filename],
        input=raw,
        capture_output=True,
        timeout=150,
        cwd=ROOT,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode or len(result.stdout) > 30 * 1024 * 1024:
        raise ValueError("parser_failed")
    body = json.loads(result.stdout.decode("utf-8"))
    if not body.get("ok"):
        raise ValueError(body.get("reason", "parser_failed"))
    return body["result"]


def run_once(factory=Session):
    with factory() as db:
        job = db.execute(
            select(DocumentJob)
            .where(
                or_(
                    DocumentJob.status == "queued",
                    (DocumentJob.status == "processing")
                    & (DocumentJob.lease_until < now()),
                )
            )
            .order_by(DocumentJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).scalar_one_or_none()
        if not job:
            return False
        r = db.get(Record, job.document_id)
        u = db.get(User, job.requested_by)
        try:
            if (
                not u
                or not r
                or r.status == "deleted"
                or r.payload.get("generation") != job.generation
            ):
                raise ValueError()
            authorize(db, u, r.patient_id, "review")
        except Exception:
            job.status = "cancelled"
            if (
                r
                and r.status != "deleted"
                and r.payload.get("generation") == job.generation
            ):
                r.payload = r.payload | {
                    "processing_status": "failed",
                    "stage": "cancelled",
                    "error": "access_revoked",
                }
                r.version += 1
            db.commit()
            return True
        if job.attempts >= 3:
            job.status = "failed"
            job.error = "retry_limit"
            r.payload = r.payload | {
                "processing_status": "failed",
                "stage": "failed",
                "error": "retry_limit",
            }
            r.version += 1
            db.commit()
            return True
        original = db.get(SourceFile, r.id)
        raw = bytes(original.data) if original else b""
        filename = r.payload["filename"]
        rid = r.id
        gen = job.generation
        jid = job.id
        actor = u.id
        pid = r.patient_id
        job.attempts += 1
        job.status = "processing"
        job.lease_until = (
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=4)
        ).isoformat()
        job.history = job.history + [
            {"stage": "extracting", "at": now(), "attempt": job.attempts}
        ]
        r.payload = r.payload | {
            "processing_status": "processing",
            "stage": "extracting",
            "error": None,
        }
        r.version += 1
        db.commit()
    error = None
    result = None
    try:
        if not original or hashlib.sha256(raw).hexdigest() != original.sha256:
            raise ValueError("integrity_mismatch")
        result = parse_subprocess(raw, filename)
    except subprocess.TimeoutExpired:
        error = "parser_timeout"
    except (ValueError, OSError, KeyError) as exc:
        safe = {
            "legacy_word_runtime_missing",
            "parser_failed",
            "encrypted_pdf",
            "content_limit",
            "page_limit",
            "worksheet_dimensions_limit",
            "cell_limit",
            "integrity_mismatch",
            "image_pixel_limit",
            "unreadable_document",
        }
        error = str(exc) if str(exc) in safe else "processing_failed"
    # Reauthorize and check generation before publishing; deletion/retry/revocation wins.
    with factory() as db:
        u = db.get(User, actor)
        try:
            authorize(db, u, pid, "review")
        except Exception:
            job = db.get(DocumentJob, jid)
            job.status = "cancelled"
            r = db.get(Record, rid)
            if r and r.status != "deleted" and r.payload.get("generation") == gen:
                r.payload = r.payload | {
                    "processing_status": "failed",
                    "stage": "cancelled",
                    "error": "access_revoked",
                }
                r.version += 1
            db.commit()
            return True
        r = db.execute(
            select(Record).where(Record.id == rid).with_for_update()
        ).scalar_one()
        job = db.get(DocumentJob, jid)
        if (
            r.status == "deleted"
            or r.payload.get("generation") != gen
            or job.status != "processing"
        ):
            return True
        if error:
            job.status = "failed"
            job.error = error
            job.history = job.history + [
                {"stage": "failed", "at": now(), "code": error}
            ]
            r.payload = r.payload | {
                "processing_status": "failed",
                "stage": "failed",
                "error": error,
            }
            r.version += 1
            db.commit()
            return True
        job.history = job.history + [
            {"stage": "structuring", "at": now()},
            {"stage": "indexing", "at": now()},
        ]
        clear_derived(db, rid)
        for n, unit in enumerate(result["units"]):
            u = DocumentUnit(document_id=rid, generation=gen, ordinal=n, **unit)
            db.add(u)
            db.flush()
            for text in split_unit(u.text):
                db.add(
                    DocumentChunk(
                        document_id=rid,
                        generation=gen,
                        unit_id=u.id,
                        kind=u.kind,
                        text=text,
                        source=u.source,
                        terms=dict(terms(text)),
                    )
                )
        for asset in result["assets"]:
            db.add(
                DocumentAsset(
                    document_id=rid,
                    generation=gen,
                    source=asset["source"],
                    mime=asset["mime"],
                    data=base64.b64decode(asset["data"], validate=True),
                )
            )
        pages = {}
        for unit in result["units"]:
            if "page" in unit["source"]:
                pages.setdefault(unit["source"]["page"], []).append(unit["text"])
        page_list = [
            {"number": n, "text": "\n\n".join(texts)}
            for n, texts in sorted(pages.items())
        ]
        r.payload = r.payload | {
            "processing_status": result["processing_status"],
            "stage": "complete",
            "text": result["text"],
            "sha256": hashlib.sha256(result["text"].encode()).hexdigest(),
            "pages": page_list,
            "page_count": len(page_list),
            "unit_count": len(result["units"]),
            "asset_count": len(result["assets"]),
            "warnings": result["warnings"],
            "error": None,
            "parser": "native + local OCR",
            "processed_at": now(),
        }
        r.version += 1
        job.status = "completed"
        job.lease_until = None
        job.history = job.history + [
            {"stage": result["processing_status"], "at": now()}
        ]
        db.add(
            Audit(
                patient_id=pid,
                actor=actor,
                action="document.processed",
                detail={
                    "document_id": rid,
                    "generation": gen,
                    "units": len(result["units"]),
                    "status": result["processing_status"],
                },
            )
        )
        db.commit()
    return True


if __name__ == "__main__":
    backfill_legacy()
    while True:
        try:
            worked = run_once()
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Document worker infrastructure error: %s", type(exc).__name__
            )
            worked = False  # never log source text, provider bodies or credentials
        time.sleep(0.2 if worked else 1)
