"""Endpoints for the two-scan Agent Analysis workflow (stages 1-2). Clinician research access only."""
import io

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import agent_activity as AC
from . import agent_analysis as A
from . import agent_explainer as X
from . import agent_ledger as L
from . import agent_runtime as R
from . import agent_visual as V
from . import agent_visual_ai as VA
from . import oasis2_api as O
from . import services
from .imaging import HEADERS, research_access
from .models import User
from .oasis2_api import AXES
from .security import get_db

router = APIRouter(prefix="/api/imaging/agent", tags=["agent analysis"])


class PairIn(BaseModel):
    earlier: str
    later: str
    scan: str = "mpr-1"


def _out(data, code=200):
    return JSONResponse(data, status_code=code, headers=HEADERS)


@router.get("/tools")
def tools(_: User = Depends(research_access)):
    return _out(A.tools())


@router.get("/pairs")
def pairs(_: User = Depends(research_access)):
    return _out({"pairs": A.candidate_pairs()})


@router.post("/validate")
def validate(body: PairIn, _: User = Depends(research_access)):
    return _out(A.validate_pair(body.earlier, body.later, body.scan))


@router.post("/runs")
def start(body: PairIn, background: BackgroundTasks, user: User = Depends(research_access), db: Session = Depends(get_db)):
    run = A.create_run(body.earlier, body.later, body.scan)
    services.audit(db, user.id, "agent_analysis.start", target=run["run_id"])
    db.commit()
    if run["state"] != "blocked":
        background.add_task(A.run_all, run["run_id"])
    return _out(run, 202 if run["state"] != "blocked" else 200)


def _get(run_id: str) -> dict:
    run = A.load_run(run_id)
    if run is None:
        raise HTTPException(404, "Unknown run.")
    return run


@router.get("/saved")
def saved(_: User = Depends(research_access)):
    return _out({"runs": A.list_runs()})


@router.get("/runs/{run_id}")
def get_run(run_id: str, _: User = Depends(research_access)):
    return _out(_get(run_id))


@router.get("/runs/{run_id}/facts")
def facts(run_id: str, _: User = Depends(research_access)):
    return _out(L.build(_get(run_id)))


@router.get("/agents/status")
def agents_status(_: User = Depends(research_access)):
    return _out(R.status())


@router.get("/runs/{run_id}/agents")
def agents_trace(run_id: str, _: User = Depends(research_access)):
    _get(run_id)
    d = A.runs_root() / run_id
    return _out({"trace": R.read(d, R.TRACE), "egress": R.read(d, R.EGRESS)})


@router.get("/runs/{run_id}/ai")
def ai_result(run_id: str, _: User = Depends(research_access)):
    _get(run_id)
    return _out({"result": X.load(A.runs_root() / run_id), "status": R.status()})


@router.post("/runs/{run_id}/ai/explain")
def ai_explain(run_id: str, _: User = Depends(research_access)):
    run = _get(run_id)
    if run["state"] in ("queued", "running", "aligned"):
        raise HTTPException(409, "Wait for the analysis to finish.")
    try:
        return _out(X.explain(run, A.runs_root() / run_id))
    except ValueError as e:
        raise HTTPException(409, str(e)) from None


@router.get("/runs/{run_id}/ai/visual")
def ai_visual_result(run_id: str, _: User = Depends(research_access)):
    _get(run_id)
    return _out({"result": VA.load(A.runs_root() / run_id), "images_allowed": R.images_allowed(), "mode": R.mode()})


@router.post("/runs/{run_id}/ai/visual")
def ai_visual(run_id: str, _: User = Depends(research_access)):
    run = _get(run_id)
    if run["state"] in ("queued", "running", "aligned"):
        raise HTTPException(409, "Wait for the analysis to finish.")
    try:
        return _out(VA.observe(run, A.runs_root() / run_id))
    except ValueError as e:
        raise HTTPException(409, str(e)) from None


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, _: User = Depends(research_access)):
    _get(run_id)
    return _out(A.cancel(run_id))


@router.post("/runs/{run_id}/retry")
def retry(run_id: str, background: BackgroundTasks, _: User = Depends(research_access)):
    old = _get(run_id)
    run = A.create_run(old["earlier"], old["later"], old["scan"], parent=run_id)
    if run["state"] != "blocked":
        background.add_task(A.run_all, run["run_id"])
    return _out(run, 202)


@router.get("/workflow")
def workflow(_: User = Depends(research_access)):
    """The workflow graph before any run: what is built, and what this server can run now. Nothing has executed."""
    al = A.tools()["alignment"]
    return _out(AC.workflow(al["available"], al["needs"]))


@router.get("/runs/{run_id}/activity")
def activity(run_id: str, after: int = 0, _: User = Depends(research_access)):
    """Nodes with status plus the execution events after ``after`` (a sequence number). Safe to repeat after a dropped connection."""
    run = _get(run_id)
    return _out(AC.activity(run, A.runs_root() / run_id, max(after, 0)))


@router.get("/runs/{run_id}/slice.png")
def slice_png(run_id: str, layer: str = "earlier", axis: int = 2, index: int = 0, _: User = Depends(research_access)):
    if layer not in ("earlier", "later_original", "later_aligned") or axis not in AXES:
        raise HTTPException(422, "Unknown layer or axis.")
    run = _get(run_id)
    data = A.layer_volume(run, layer)
    if data is None:
        raise HTTPException(404, "This layer is not available for this run.")
    if not 0 <= index < data.shape[axis]:
        raise HTTPException(422, f"index must be between 0 and {data.shape[axis] - 1}.")
    return Response(V.png(V.render_slice(run, layer, axis, index)), media_type="image/png", headers=HEADERS)


PALETTE = [(230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200), (245, 130, 48), (145, 30, 180), (70, 240, 240), (240, 50, 230),
           (210, 245, 60), (250, 190, 212), (0, 128, 128), (220, 190, 255), (170, 110, 40), (255, 250, 200), (128, 0, 0), (170, 255, 195)]


@router.get("/runs/{run_id}/overlay.png")
def overlay_png(run_id: str, layer: str = "regions", axis: int = 2, index: int = 0, label: int = 0, _: User = Depends(research_access)):
    """Transparent colour layer for one slice. regions: earlier segmentation. change: labels that differ after alignment."""
    import numpy as np
    from PIL import Image
    if layer not in ("regions", "change") or axis not in AXES:
        raise HTTPException(422, "Unknown layer or axis.")
    run = _get(run_id)
    e, l = A.layer_labels(run, "earlier_seg"), A.layer_labels(run, "later_seg_aligned")
    if e is None or l is None:
        raise HTTPException(404, "No segmentation layers for this run: the anatomical step has not run.")
    if not 0 <= index < e.shape[axis]:
        raise HTTPException(422, f"index must be between 0 and {e.shape[axis] - 1}.")
    pe, pl = np.take(e, index, axis=axis), np.take(l, index, axis=axis)
    rgba = np.zeros(pe.shape + (4,), np.uint8)
    if layer == "regions":
        for lab in np.unique(pe):
            if lab == 0 or (label and lab != label):
                continue
            rgba[pe == lab] = (*PALETTE[int(lab) % len(PALETTE)], 255)
    else:  # loss in red (earlier only), gain in blue (later only), for the chosen region or all labelled regions
        sel = (lambda a: a == label) if label else (lambda a: a > 0)
        rgba[sel(pe) & ~sel(pl)] = (220, 40, 40, 255)
        rgba[sel(pl) & ~sel(pe)] = (40, 90, 220, 255)
    image = Image.fromarray(np.rot90(rgba), mode="RGBA")
    zooms = run["validation"]["checks"]["earlier"]["voxel_mm"]
    i, j = [k for k in range(3) if k != axis]
    zi, zj = zooms[i] or 1.0, zooms[j] or 1.0
    if abs(zi - zj) > 1e-3:
        m = min(zi, zj)
        image = image.resize((max(1, round(image.width * zi / m)), max(1, round(image.height * zj / m))), Image.NEAREST)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png", headers=HEADERS)
