"""Native MRI intake/QC/display preparation. No FreeSurfer or LLM calls.

All original uploads are immutable. This first worker creates display volumes only;
it never describes a technical check as anatomical segmentation or diagnosis.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import uuid

from sqlalchemy import select, update

from .models import NativeRun, NativeScan, now
from . import services as S

SUBJECT = "OAS1_0001_MR1"
MAX_UPLOAD = 80 * 1024 * 1024
MAX_EXPANDED = 160 * 1024 * 1024
MAX_VOXELS = 32_000_000
_WORKER_SLOT = threading.BoundedSemaphore(1)


def root() -> Path:
    return Path(os.environ.get("NEUROTWIN_NATIVE_ROOT", Path(__file__).resolve().parents[1] / "imaging_data" / "native"))


def stages() -> list[dict]:
    return [{"id": key, "name": title, "status": status, "detail": detail} for key, title, status, detail in [
        ("intake", "Original scan preserved", "succeeded", "Source files and SHA-256 checksums recorded."),
        ("validation", "Geometry & data validation", "pending", "Check volume, affine and finite intensities."),
        ("display", "Native MRI display preparation", "pending", "Create a display volume; preserve the original."),
        ("segmentation", "Anatomical segmentation", "blocked", "No evaluated native segmentation model connected."),
        ("measurements", "Regional anatomy measurements", "blocked", "Requires accepted native segmentation and measurement methods."),
        ("agents", "AI evidence review", "blocked", "Agent execution and real-data provider permission are not enabled."),
        ("forecast", "Future prediction", "blocked", "No evaluated forecasting model connected."),
    ]]


def dependencies_available() -> bool:
    try:
        import nibabel  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def intake(db, owner: str, files: list[tuple[str, bytes]]) -> tuple[NativeScan, NativeRun]:
    suffixes = []
    clean = []
    for original, content in files:
        name = original.replace("\\", "/").split("/")[-1][:160]
        suffix = ".nii.gz" if name.lower().endswith(".nii.gz") else Path(name).suffix.lower()
        if suffix not in {".nii", ".nii.gz", ".img", ".hdr"} or not content:
            raise S.Refused(422, "Provide a NIfTI volume (.nii/.nii.gz) or a complete .hdr/.img pair.")
        suffixes.append(suffix)
        clean.append((name, suffix, content))
    if sorted(suffixes) not in [[".nii"], [".nii.gz"], [".hdr", ".img"]]:
        raise S.Refused(422, "Import one NIfTI volume or exactly one matching .hdr/.img pair.")
    if len(clean) == 2 and Path(clean[0][0]).stem.lower() != Path(clean[1][0]).stem.lower():
        raise S.Refused(422, "The .hdr and .img files must have matching base names.")
    if sum(len(f[2]) for f in clean) > MAX_UPLOAD:
        raise S.Refused(413, "The selected source files exceed the 80 MiB import limit.")
    storage = root(); storage.mkdir(parents=True, exist_ok=True)
    scan_id = str(uuid.uuid4()); target = storage / scan_id
    with tempfile.TemporaryDirectory(prefix="intake-", dir=storage) as tmp:
        work = Path(tmp); source = work / "source"; source.mkdir()
        records = []
        for name, suffix, content in clean:
            stored = f"original{suffix}"; (source / stored).write_bytes(content)
            records.append({"original_name": name, "stored_name": stored, "bytes": len(content),
                            "sha256": hashlib.sha256(content).hexdigest()})
        work.rename(target)
    scan = NativeScan(id=scan_id, owner_id=owner, subject=SUBJECT, declared_modality="T1w", files=records)
    run = NativeRun(id=str(uuid.uuid4()), scan_id=scan_id, status="queued", stages=stages(), findings=[])
    try:
        db.add(scan); db.flush(); db.add(run)
        S.audit(db, owner, "native_imaging.import", target=scan_id)
        db.commit()
    except Exception:
        db.rollback(); shutil.rmtree(target)
        raise
    return scan, run


def run_out(scan: NativeScan, run: NativeRun) -> dict:
    return {"id": run.id, "scan_id": scan.id, "subject": scan.subject, "status": run.status,
            "parent_run_id": run.parent_run_id, "stages": run.stages, "findings": run.findings,
            "result": run.result, "error": run.error, "retryable": run.retryable,
            "producer_version": run.producer_version, "files": scan.files,
            "created_at": run.created_at.isoformat(), "updated_at": run.updated_at.isoformat()}


def owned_run(db, owner: str, run_id: str):
    run = db.get(NativeRun, run_id)
    scan = db.get(NativeScan, run.scan_id) if run else None
    if not scan or scan.owner_id != owner:
        raise S.Refused(404, "Native processing run not found.")
    return scan, run


def mark(db, run: NativeRun, stage: str, status: str, detail: str):
    run.stages = [{**s, "status": status, "detail": detail} if s["id"] == stage else s for s in run.stages]
    run.updated_at = now(); db.commit()


def _cancelled(db, run: NativeRun) -> bool:
    db.refresh(run)
    return run.status == "cancelled"


def _load_source(source: Path, work: Path):
    import nibabel as nib
    import numpy as np
    if (source / "original.nii.gz").exists():
        dest = work / "expanded.nii"
        total = 0
        with gzip.open(source / "original.nii.gz", "rb") as stream, dest.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_EXPANDED:
                    raise ValueError("Expanded MRI exceeds the 160 MiB preparation limit.")
                out.write(chunk)
        path = dest
    else:
        path = source / ("original.nii" if (source / "original.nii").exists() else "original.hdr")
    image = nib.load(path)
    stored_shape = image.shape
    # Some structural Analyze/NIfTI acquisitions store a single volume as (X,Y,Z,1).
    # Remove only singleton trailing dimensions; a real temporal series remains unsupported.
    image = nib.squeeze_image(image)
    shape = image.shape
    if len(shape) != 3 or any(n < 16 or n > 512 for n in shape) or int(np.prod(shape)) > MAX_VOXELS:
        raise ValueError("Expected a single 3D MRI volume, 16–512 voxels per axis, within the voxel limit.")
    if image.get_data_dtype().kind not in "iuf":
        raise ValueError("Unsupported MRI data type.")
    if not np.isfinite(image.affine).all() or abs(np.linalg.det(image.affine[:3, :3])) < 1e-8:
        raise ValueError("Invalid or singular MRI coordinate transform.")
    zooms = image.header.get_zooms()[:3]
    if any(not np.isfinite(z) or z < .2 or z > 10 for z in zooms):
        raise ValueError("Voxel spacing is outside the supported 0.2–10 mm range.")
    values = np.asarray(image.dataobj, dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError("MRI contains non-finite intensities.")
    low, high = np.percentile(values, [1, 99.5])
    if high <= low:
        raise ValueError("MRI has insufficient intensity variation for display preparation.")
    verified_frame = isinstance(image, (nib.Nifti1Image, nib.Nifti2Image)) and (
        int(image.header["sform_code"]) > 0 or int(image.header["qform_code"]) > 0)
    findings = [{"code": "modality_declared", "severity": "review", "message": "T1-weighting is user-declared; array checks do not verify the acquisition protocol."},
                {"code": "anatomical_qc_pending", "severity": "review", "message": "Technical validation does not establish adequate brain coverage, low motion or anatomical correctness."}]
    if not verified_frame:
        findings.append({"code": "orientation_unverified", "severity": "review", "message": "No explicit NIfTI spatial transform is available. Axes are shown as voxel axes; anatomical directions need independent confirmation."})
    if max(zooms) / min(zooms) > 1.5:
        findings.append({"code": "anisotropic", "severity": "review", "message": "Unequal voxel spacing requires protocol-specific suitability review."})
    # Reorientation is a transpose/flip only, not skull stripping, registration or segmentation.
    display_image = nib.as_closest_canonical(image) if verified_frame else image
    display_values = np.asarray(display_image.dataobj, dtype=np.float32)
    strides = [max(1, int(np.ceil(n / 256))) for n in display_values.shape]
    preview = display_values[::strides[0], ::strides[1], ::strides[2]]
    preview = np.clip((preview - low) * 255 / (high - low), 0, 255).astype("u1")
    affine = display_image.affine @ np.diag([*strides, 1])
    result = {"source_shape": [int(v) for v in stored_shape], "shape": [int(v) for v in preview.shape],
              "source_spacing_mm": [float(v) for v in zooms], "source_affine": image.affine.tolist(),
              "display_affine": affine.tolist(), "display_spacing_mm": np.linalg.norm(affine[:3, :3], axis=0).tolist(),
              "axis_codes": list(nib.aff2axcodes(display_image.affine)) if verified_frame else None,
              "spatial_frame_explicit": verified_frame, "display_percentiles": [float(low), float(high)],
              "dtype": "uint8", "array_order": "C", "kind": "native_mri_display", "downsample_strides": strides,
              "anatomical_qc": "pending", "segmentation_available": False, "prediction_available": False}
    return preview, result, findings


def process(factory, run_id: str, storage: Path):
    # Bound peak image-array memory. Waiting attempts remain queued and cancellable.
    with _WORKER_SLOT:
        _process(factory, run_id, storage)


def _process(factory, run_id: str, storage: Path):
    """Single-process background execution; the DB is the durable source of run state."""
    with factory() as db:
        claimed = db.execute(update(NativeRun).where(NativeRun.id == run_id, NativeRun.status == "queued")
                             .values(status="running", updated_at=now())).rowcount
        db.commit()
        if not claimed:
            return
        run = db.get(NativeRun, run_id); scan = db.get(NativeScan, run.scan_id)
        artifact_dir = storage / scan.id / "runs" / run.id
        try:
            mark(db, run, "validation", "running", "Reading original MRI and checking supported geometry and data.")
            artifact_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="work-", dir=artifact_dir) as tmp:
                for record in scan.files:
                    path = storage / scan.id / "source" / record["stored_name"]
                    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                        raise ValueError("Source checksum mismatch. Import an intact original instead of retrying.")
                preview, result, findings = _load_source(storage / scan.id / "source", Path(tmp))
                if _cancelled(db, run):
                    return
                run.findings = findings
                mark(db, run, "validation", "succeeded", "Technical checks passed; acquisition and anatomical quality still require review.")
                mark(db, run, "display", "running", "Preparing a native display buffer with documented intensity scaling.")
                (Path(tmp) / "volume.bin").write_bytes(preview.tobytes(order="C"))
                (Path(tmp) / "manifest.json").write_text(json.dumps(result), encoding="utf-8")
                if _cancelled(db, run):
                    return
                for name in ("volume.bin", "manifest.json"):
                    (Path(tmp) / name).replace(artifact_dir / name)
                run.result = result
                mark(db, run, "display", "succeeded", "Native display prepared from the original scan. No imported segmentation or mesh used.")
                changed = db.execute(update(NativeRun).where(NativeRun.id == run.id, NativeRun.status == "running")
                                     .values(status="awaiting_review", updated_at=now())).rowcount
                if changed:
                    S.audit(db, scan.owner_id, "native_imaging.prepared", target=run.id)
                db.commit()
        except Exception as exc:
            db.rollback(); db.refresh(run)
            if run.status == "cancelled":
                return
            if isinstance(exc, (gzip.BadGzipFile, EOFError)):
                message, retryable = "The compressed MRI is invalid or incomplete. Import an intact source volume.", False
            elif isinstance(exc, ValueError):
                message, retryable = str(exc)[:300], False
            elif isinstance(exc, ImportError):
                message, retryable = "Native imaging dependencies are unavailable on the server.", True
            elif isinstance(exc, OSError):
                message, retryable = "MRI could not be read or stored. Check source integrity and available disk space.", True
            else:
                message, retryable = "MRI preparation failed. The source may be malformed or unsupported.", False
            run.status = "failed"; run.error = message; run.retryable = retryable
            run.stages = [{**s, "status": "failed", "detail": message} if s["status"] == "running"
                          else {**s, "status": "skipped", "detail": "A required stage failed."} if s["status"] == "pending" else s for s in run.stages]
            run.updated_at = now(); S.audit(db, scan.owner_id, "native_imaging.failed", target=run.id); db.commit()


def recover_interrupted(db):
    """On single-server startup, stale attempts require explicit retry, not silent success."""
    for run in db.scalars(select(NativeRun).where(NativeRun.status.in_(["queued", "running"]))):
        run.status = "failed"; run.error = "Processing was interrupted by a server restart. You may retry this attempt."
        run.retryable = True; run.updated_at = now()
        run.stages = [{**s, "status": "failed", "detail": run.error} if s["status"] in {"running", "pending"} else s for s in run.stages]
    db.commit()
