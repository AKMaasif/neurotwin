"""Read-only, locally prepared research case. No linkage to synthetic participants.

Only explicitly configured research users may access the case, including every
binary artifact request. No archive or filesystem paths are accepted from clients.
"""
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .models import User
from .security import current_user, get_db
from . import services

router = APIRouter(prefix="/api/imaging", tags=["research imaging"])
SUBJECT = "OAS1_0001_MR1"
HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


def research_access(request: Request, user: User = Depends(current_user)) -> User:
    configured = os.environ.get("NEUROTWIN_IMAGING_USERS", "")
    allowed = {v.strip() for v in configured.split(",") if v.strip()}
    if user.role != "clinician" or user.id not in allowed:
        raise HTTPException(403, "Research imaging is available only to configured research users.")
    return user


def assets() -> Path:
    root = Path(os.environ.get("NEUROTWIN_IMAGING_ROOT", Path(__file__).resolve().parents[1] / "imaging_data"))
    return root / SUBJECT / "assets"


@router.get("/case")
def case(user: User = Depends(research_access), db: Session = Depends(get_db)):
    path = assets() / "manifest.json"
    if not path.is_file():
        raise HTTPException(404, "Research case is not prepared. Run the local preparation script first.")
    manifest = json.loads(path.read_text())
    services.audit(db, user.id, "research_imaging.view", target="local-research-case")
    db.commit()
    return JSONResponse(manifest, headers=HEADERS)


def allowed_artifacts() -> set[str]:
    files = {"volume.bin", "labels.bin"}
    for hemi in ("lh", "rh"):
        files.update({f"{hemi}.regions.json", f"{hemi}.annotation.bin", f"{hemi}.thickness.bin"})
        for surface in ("pial", "white", "inflated"):
            files.update({f"{hemi}.{surface}.vertices.bin", f"{hemi}.{surface}.faces.bin"})
    return files


@router.get("/artifacts/{name}")
def artifact(name: str, _: User = Depends(research_access)):
    if name not in allowed_artifacts():
        raise HTTPException(404, "Artifact not found.")
    path = assets() / name
    if not path.is_file():
        raise HTTPException(404, "Artifact not found.")
    return FileResponse(path, media_type="application/json" if name.endswith(".json") else "application/octet-stream",
                        headers=HEADERS)
