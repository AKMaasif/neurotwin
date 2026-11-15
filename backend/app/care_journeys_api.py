"""Authenticated care-journey links and explicit follow-up actions."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import care_journeys as J
from .models import User
from .security import current_user, get_db
from .services import audit

router = APIRouter(prefix="/api/care-journeys", tags=["care journeys"])


class UpdateIn(BaseModel):
    expected_revision: int = Field(ge=1)
    plan_id: int | None = Field(default=None, ge=1)
    analysis_run_id: str | None = Field(default=None, pattern=r"^ah-[0-9a-f]{12}$")
    next_action: str | None = Field(default=None, max_length=300)
    follow_up_on: str | None = Field(default=None, max_length=10)
    outcome: Literal["open", "follow_up_required", "resolved", "referred", "closed_no_action"] | None = None
    note: str = Field(default="", max_length=500)


@router.post("/from-concern/{concern_id}")
def create(concern_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return J.out(db, J.from_concern(db, user, concern_id), user)


@router.get("/participants/{pid}")
def listing(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = J.list_for(db, user, pid)
    audit(db, user.id, "care_journey.viewed", pid, None)
    db.commit()
    return result


@router.get("/{jid}")
def detail(jid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = J.get(db, user, jid)
    result = J.out(db, row, user)
    audit(db, user.id, "care_journey.viewed", row.participant_id, f"journey:{jid}")
    db.commit()
    return result


@router.post("/{jid}")
def update(jid: int, body: UpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = J.get(db, user, jid, write=True)
    return J.out(db, J.update(db, user, row, body.model_dump(exclude_unset=True)), user)
