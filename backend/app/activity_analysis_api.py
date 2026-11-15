"""Endpoints for "Analyze activity history". Clinicians with a clinical-review grant for the person only. A run exists only
because a clinician pressed the button; nothing here is scheduled or started by a page load."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import activity_analysis as AA
from . import services
from .models import User
from .security import current_user, get_db, require_evidence_access

router = APIRouter(prefix="/api/activity-analysis", tags=["activity analysis"])
NOT_FOUND = "Not found, or you do not have access."


def _clinician(user: User) -> User:
    if user.role != "clinician":
        raise HTTPException(404, NOT_FOUND)
    return user


def _run_for(run_id: str, db: Session, user: User) -> dict:
    _clinician(user)
    run = AA.load(run_id)
    if run is None:
        raise HTTPException(404, NOT_FOUND)
    require_evidence_access(db, user, run["participant_id"])
    return run


class StartIn(BaseModel):
    range_days: int = 183


class DecisionIn(BaseModel):
    kind: str
    index: int
    decision: str
    note: str | None = Field(default=None, max_length=300)


class ReviewIn(BaseModel):
    decisions: list[DecisionIn] = Field(max_length=60)
    note: str = Field(default="", max_length=500)


@router.get("/roster")
def roster(user: User = Depends(current_user)):
    _clinician(user)
    return AA.roster()


@router.get("/participants/{pid}/runs")
def runs(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _clinician(user)
    require_evidence_access(db, user, pid)
    return AA.list_runs(pid)


@router.post("/participants/{pid}/runs")
def start(pid: str, body: StartIn, background: BackgroundTasks, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _clinician(user)
    require_evidence_access(db, user, pid)
    if body.range_days not in AA.RANGES:
        raise HTTPException(422, "Choose 6 weeks, 3 months or 6 months.")
    person = db.get(User, pid)
    run = AA.create_run(person, user, body.range_days)
    services.audit(db, user.id, "activity_analysis.start", pid, run["run_id"])
    db.commit()
    factory = request.app.state.db.SessionLocal

    def work():
        with factory() as s:
            AA.execute(run["run_id"], s)

    background.add_task(work)
    return run


@router.get("/runs/{run_id}")
def get_run(run_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _run_for(run_id, db, user)


@router.post("/runs/{run_id}/review")
def review(run_id: str, body: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _run_for(run_id, db, user)
    try:
        run = AA.review(run_id, user, [d.model_dump() for d in body.decisions], body.note)
    except ValueError as e:
        raise HTTPException(422, str(e))
    services.audit(db, user.id, "activity_analysis.review", run["participant_id"], run_id)
    db.commit()
    return run
