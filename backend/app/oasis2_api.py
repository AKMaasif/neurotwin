"""Read-only OASIS-2 visit comparison for configured research users.

Serves the manifest and 8-bit display slices of locally extracted raw scans. Clients send only a subject or visit id
matching the dataset's pattern; no file paths are accepted. Slices are in voxel axes: orientation is not verified for
these Analyze files, and visits are not registered to each other.
"""
import io
import json
import os
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from .imaging import HEADERS, research_access
from .models import User
from .security import get_db
from . import services

router = APIRouter(prefix="/api/imaging/oasis2", tags=["research imaging"])
SUBJECT = re.compile(r"^OAS2_\d{4}$")
VISIT = re.compile(r"^OAS2_\d{4}_MR\d{1,2}$")
SCAN = re.compile(r"^mpr-\d{1,2}$")
AXES = (0, 1, 2)  # voxel axes of the file; anatomical names are not used because orientation is unverified


def root() -> Path:
    base = Path(os.environ.get("NEUROTWIN_IMAGING_ROOT", Path(__file__).resolve().parents[1] / "imaging_data"))
    return base / "oasis2"


def _manifest() -> dict:
    path = root() / "manifest.json"
    if not path.is_file():
        raise HTTPException(404, "The OASIS-2 manifest has not been built. Run scripts/oasis2_manifest.py first.")
    return json.loads(path.read_text())


def _raw_dir(mri_id: str) -> Path | None:
    """The extracted RAW folder of a visit, searched only under the fixed extraction root."""
    base = root() / "extracted"
    if not base.is_dir():
        return None
    for part in sorted(base.iterdir()):
        candidate = part / mri_id / "RAW"
        if candidate.is_dir():
            return candidate
    return None


def _scans(mri_id: str) -> list[str]:
    raw = _raw_dir(mri_id)
    if raw is None:
        return []
    return sorted(p.name[:-len(".nifti.hdr")] for p in raw.glob("mpr-*.nifti.hdr") if (raw / p.name.replace(".hdr", ".img")).is_file())


@lru_cache(maxsize=3)
def _volume(path: str, mtime: float):
    import nibabel as nib
    import numpy as np
    image = nib.load(path)
    data = np.asarray(image.dataobj, dtype=np.float32)
    while data.ndim > 3 and data.shape[-1] == 1:
        data = data[..., 0]
    if data.ndim != 3:
        raise ValueError("not a single 3D volume")
    nonzero = data[data > 0]
    lo, hi = (np.percentile(nonzero, [1, 99]) if nonzero.size else (0.0, 1.0))
    return data, float(lo), float(max(hi, lo + 1e-6)), tuple(float(v) for v in image.header.get_zooms()[:3])


def _load(mri_id: str, scan: str):
    if not VISIT.match(mri_id) or not SCAN.match(scan):
        raise HTTPException(404, "Unknown visit or scan.")
    raw = _raw_dir(mri_id)
    hdr = None if raw is None else raw / f"{scan}.nifti.hdr"
    if hdr is None or not hdr.is_file():
        raise HTTPException(404, "This visit's scan has not been extracted locally yet.")
    try:
        return _volume(str(hdr), hdr.stat().st_mtime)
    except Exception as exc:  # unreadable or not a single volume: say so, never show a blank image as normal
        raise HTTPException(422, f"The scan could not be read as one 3D volume ({type(exc).__name__}).") from exc


@router.get("/subjects")
def subjects(user: User = Depends(research_access), db: Session = Depends(get_db)):
    manifest = _manifest()
    out = []
    for s in manifest["subjects"]:
        visits = [{**v, "prepared": bool(_scans(v["mri_id"]))} for v in s["visits"]]
        out.append({"subject_id": s["subject_id"], "group_label_from_dataset": s["group_label_from_dataset"],
                    "level1_compare": s["level1_compare"], "level2_trend": s["level2_trend"], "visits": visits,
                    "ready": sum(v["prepared"] for v in visits) >= 2})
    services.audit(db, user.id, "research_imaging.oasis2_list", target="oasis2")
    db.commit()
    return JSONResponse({"subjects": out, "summary": manifest["summary"]}, headers=HEADERS)


@router.get("/visits/{mri_id}/info")
def info(mri_id: str, scan: str = "mpr-1", _: User = Depends(research_access)):
    data, lo, hi, zooms = _load(mri_id, scan)
    return JSONResponse({"mri_id": mri_id, "scan": scan, "scans": _scans(mri_id), "shape": list(data.shape), "voxel_mm": list(zooms),
                         "frame": "voxel axes; anatomical orientation not verified"}, headers=HEADERS)


@router.get("/visits/{mri_id}/slice.png")
def slice_png(mri_id: str, axis: int = 2, index: int = 0, scan: str = "mpr-1", user: User = Depends(research_access)):
    if axis not in AXES:
        raise HTTPException(422, "axis must be 0, 1 or 2 (voxel axes).")
    import numpy as np
    from PIL import Image
    data, lo, hi, zooms = _load(mri_id, scan)
    ax = axis
    if not 0 <= index < data.shape[ax]:
        raise HTTPException(422, f"index must be between 0 and {data.shape[ax] - 1}.")
    plane = np.take(data, index, axis=ax)
    gray = np.clip((plane - lo) / (hi - lo), 0, 1) * 255
    buffer = io.BytesIO()
    image = Image.fromarray(np.rot90(gray).astype(np.uint8), mode="L")
    i, j = [k for k in range(3) if k != ax]  # the plane's two voxel axes; rot90 puts i across and j down
    zi, zj = (zooms[i] or 1.0), (zooms[j] or 1.0)
    if abs(zi - zj) > 1e-3:  # show true proportions when voxels are not cubes
        m = min(zi, zj)
        image = image.resize((max(1, round(image.width * zi / m)), max(1, round(image.height * zj / m))), Image.BILINEAR)
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png", headers=HEADERS)
