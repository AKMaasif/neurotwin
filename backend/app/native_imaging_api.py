"""Authorized native scan intake and durable single-server workflow endpoints."""
import tarfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from . import native_imaging as N
from . import services as S
from .imaging import HEADERS, research_access
from .models import NativeRun, NativeScan, User, now
from .security import get_db

router = APIRouter(prefix="/api/imaging/native", tags=["native research imaging"])


class ImagingRequestGuard(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/api/imaging/native/import" and request.method == "POST":
            try:
                length = int(request.headers.get("content-length", "-1"))
            except ValueError:
                return JSONResponse({"detail": "Invalid upload length."}, status_code=400)
            if length < 0:
                return JSONResponse({"detail": "Provide an upload with a known content length."}, status_code=411)
            if length > N.MAX_UPLOAD + 1024 * 1024:
                return JSONResponse({"detail": "The upload exceeds the 80 MiB source-file limit."}, status_code=413)
        response = await call_next(request)
        if request.url.path.startswith("/api/imaging/"):
            for key, value in HEADERS.items():
                response.headers[key] = value
        return response


def runtime_available():
    if not N.dependencies_available():
        raise HTTPException(503, "Native MRI support is not installed on this server.")


@router.get("/runs")
def runs(user: User = Depends(research_access), db: Session = Depends(get_db)):
    rows = db.execute(select(NativeScan, NativeRun).join(NativeRun, NativeScan.id == NativeRun.scan_id)
                      .where(NativeScan.owner_id == user.id).order_by(NativeRun.created_at.desc()).limit(50))
    return {"available": N.dependencies_available(), "subject": N.SUBJECT,
            "runs": [N.run_out(scan, run) for scan, run in rows]}


@router.post("/import")
async def import_scan(request: Request, tasks: BackgroundTasks, files: list[UploadFile] = File(...),
                      confirmed: bool = Form(False), user: User = Depends(research_access), db: Session = Depends(get_db)):
    runtime_available()
    if not confirmed:
        raise HTTPException(422, "Confirm that the source is this participant's intended T1 structural MRI.")
    if len(files) not in (1, 2):
        raise HTTPException(422, "Select one NIfTI volume or one .hdr/.img pair.")
    total = 0; payload = []
    for file in files:
        chunks = []
        try:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > N.MAX_UPLOAD:
                    raise HTTPException(413, "The source files exceed the 80 MiB import limit.")
                chunks.append(chunk)
            payload.append((file.filename or "", b"".join(chunks)))
        finally:
            await file.close()
    scan, run = N.intake(db, user.id, payload)
    tasks.add_task(N.process, request.app.state.db.SessionLocal, run.id, N.root())
    return N.run_out(scan, run)


@router.post("/sample")
def sample(request: Request, tasks: BackgroundTasks, user: User = Depends(research_access), db: Session = Depends(get_db)):
    """Import exactly the already-downloaded participant's ORIGINAL raw acquisition, not derivatives."""
    runtime_available()
    archive = Path(__file__).resolve().parents[2] / "OASIS-1 (Open Access Series of Imaging Studies)" / "OASIS-1 Demographic and Clinical Data" / "oasis_cross-sectional_disc1.tar.gz"
    if not archive.is_file():
        raise HTTPException(404, "The original local OASIS archive is unavailable. Import your MRI files instead.")
    stem = f"{N.SUBJECT}_mpr-1_anon"
    wanted = {f"disc1/{N.SUBJECT}/RAW/{stem}{suffix}" for suffix in (".hdr", ".img")}
    payload = []
    try:
        with tarfile.open(archive, "r|gz") as tf:
            for member in tf:
                if member.name not in wanted or not member.isfile():
                    continue
                if member.size > N.MAX_UPLOAD:
                    raise HTTPException(413, "The sample exceeds the import limit.")
                with tf.extractfile(member) as stream:
                    payload.append((member.name.split("/")[-1], stream.read(N.MAX_UPLOAD + 1)))
                if len(payload) == 2:
                    break
    except (tarfile.TarError, OSError):
        raise HTTPException(422, "The original sample archive could not be read.") from None
    if len(payload) != 2:
        raise HTTPException(422, "The original sample header/image pair was not found.")
    scan, run = N.intake(db, user.id, payload)
    tasks.add_task(N.process, request.app.state.db.SessionLocal, run.id, N.root())
    return N.run_out(scan, run)


@router.get("/runs/{run_id}")
def run_detail(run_id: str, user: User = Depends(research_access), db: Session = Depends(get_db)):
    scan, run = N.owned_run(db, user.id, run_id)
    return N.run_out(scan, run)


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, user: User = Depends(research_access), db: Session = Depends(get_db)):
    scan, run = N.owned_run(db, user.id, run_id)
    if run.status not in {"queued", "running"}:
        raise HTTPException(409, "Only queued or running attempts can be cancelled.")
    run.status = "cancelled"; run.updated_at = now()
    run.stages = [{**stage, "status": "cancelled", "detail": "Cancelled by the research user."}
                  if stage["status"] in {"pending", "running"} else stage for stage in run.stages]
    S.audit(db, user.id, "native_imaging.cancel", target=run.id); db.commit()
    return N.run_out(scan, run)


@router.post("/runs/{run_id}/retry")
def retry(run_id: str, request: Request, tasks: BackgroundTasks,
          user: User = Depends(research_access), db: Session = Depends(get_db)):
    runtime_available()
    scan, old = N.owned_run(db, user.id, run_id)
    if old.status not in {"failed", "cancelled"} or (old.status == "failed" and not old.retryable):
        raise HTTPException(409, "This attempt cannot be retried. Resolve input/QC issues with a corrected import.")
    existing = db.scalar(select(NativeRun).where(NativeRun.scan_id == scan.id, NativeRun.status.in_(["queued", "running"])))
    if existing:
        raise HTTPException(409, "This scan already has an active processing attempt.")
    run = NativeRun(id=str(uuid.uuid4()), scan_id=scan.id, parent_run_id=old.id, stages=N.stages(), findings=[], status="queued")
    db.add(run); S.audit(db, user.id, "native_imaging.retry", target=run.id); db.commit()
    tasks.add_task(N.process, request.app.state.db.SessionLocal, run.id, N.root())
    return N.run_out(scan, run)


@router.get("/runs/{run_id}/volume")
def volume(run_id: str, user: User = Depends(research_access), db: Session = Depends(get_db)):
    scan, run = N.owned_run(db, user.id, run_id)
    if run.status != "awaiting_review" or not run.result:
        raise HTTPException(409, "A complete native display volume is not available for this attempt.")
    path = N.root() / scan.id / "runs" / run.id / "volume.bin"
    if not path.is_file():
        raise HTTPException(404, "Prepared volume not found.")
    S.audit(db, user.id, "native_imaging.view", target=run.id); db.commit()
    return FileResponse(path, media_type="application/octet-stream", headers=HEADERS)
