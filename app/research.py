"""Synthetic research session contracts, separate from clinical assessments."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .db import Audit, Record, User, get_db, now
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/research")
PROTOCOL = {
    "id": "synthetic-capture",
    "version": "1",
    "purpose": "Software workflow testing only; no medical assessment or score",
    "consent_version": "synthetic-research-1",
    "consent_text": "This optional synthetic workflow tests software only. It is not a medical assessment. Session actions and device category are stored for software review. You may stop or withdraw; withdrawal retains the audit record and is not data deletion. No microphone or camera recording is collected by this workflow.",
    "clinical_use": False,
}


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=8, max_length=100)
    protocol_id: Literal["synthetic-capture"]
    protocol_version: Literal["1"]


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=8, max_length=100)
    expected_version: int = Field(ge=1)
    action: Literal["consent", "complete", "interrupt", "cancel", "withdraw"]
    consent_version: str | None = Field(default=None, max_length=80)
    quality: Literal["usable", "poor", "interrupted"] | None = None
    mode: Literal["self", "assisted", "video"] | None = None
    device_class: Literal["phone", "tablet", "desktop", "unknown"] | None = None


def access(db, actor, pid):
    patient = authorize(db, actor, pid, "assessment")
    if actor.role not in {"participant", "clinician"} or not patient.synthetic:
        raise HTTPException(
            403, "Research capture is restricted to synthetic workspaces"
        )


@router.get("/sessions")
def sessions(pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    from .main import pack

    access(db, u, pid)
    rows = db.query(Record).filter_by(patient_id=pid, kind="research_session").all()
    # Participants see assignments and their own consented sessions only.
    rows = [
        r
        for r in rows
        if u.role == "clinician" or r.payload.get("participant_id") in (None, u.id)
    ]
    db.add(
        Audit(patient_id=pid, actor=u.id, action="research.sessions.read", detail={})
    )
    db.commit()
    return {
        "protocol": PROTOCOL,
        "sessions": [pack(r) for r in rows],
        "clinical_use": False,
    }


@router.post("/sessions")
def assign(
    pid: str,
    body: Assignment,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import pack, receipt, replay

    access(db, u, pid)
    authorize(db, u, pid, "review")
    if u.role != "clinician":
        raise HTTPException(403, "Clinician assignment required")
    cmd = body.model_dump() | {"patient_id": pid, "operation": "research.assign"}
    h, previous = replay(db, u, cmd)
    if previous is not None:
        return previous
    row = Record(
        patient_id=pid,
        kind="research_session",
        status="awaiting_consent",
        payload={
            "protocol": dict(PROTOCOL),
            "assigned_by": u.id,
            "participant_id": None,
            "clinical_use": False,
            "source_type": "synthetic_research_workflow",
            "events": [],
        },
    )
    db.add(row)
    db.flush()
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="research.assigned",
            detail={"session_id": row.id},
        )
    )
    return receipt(db, u, cmd, h, pack(row))


@router.post("/sessions/{rid}/transition")
def transition(
    pid: str,
    rid: str,
    body: Transition,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import pack, receipt, replay, scoped_record

    access(db, u, pid)
    row = scoped_record(db, pid, rid, "research_session")
    if u.role != "participant":
        raise HTTPException(
            403, "Participant action required; proxy consent is unavailable"
        )
    if row.payload.get("participant_id") not in (None, u.id):
        raise HTTPException(403, "Session belongs to another participant")
    cmd = body.model_dump() | {
        "patient_id": pid,
        "session_id": rid,
        "operation": "research.transition",
    }
    h, previous = replay(db, u, cmd)
    if previous is not None:
        return previous
    if row.version != body.expected_version:
        raise HTTPException(409, "Session changed; refresh before continuing")
    allowed = {
        "consent": {"awaiting_consent"},
        "complete": {"active"},
        "interrupt": {"active"},
        "cancel": {"awaiting_consent", "active"},
        "withdraw": {"active", "completed", "interrupted"},
    }
    if row.status not in allowed[body.action]:
        raise HTTPException(409, "Action unavailable in current session state")
    if (
        body.action in {"consent", "complete"}
        and row.payload.get("protocol") != PROTOCOL
    ):
        raise HTTPException(409, "Protocol changed; a new assignment is required")
    if body.action == "consent" and body.consent_version != PROTOCOL["consent_version"]:
        raise HTTPException(409, "Current consent text must be accepted explicitly")
    if body.action == "complete" and (
        body.quality not in {"usable", "poor"}
        or body.mode is None
        or body.device_class is None
    ):
        raise HTTPException(
            422, "Completion requires quality, mode and device provenance"
        )
    if body.action != "complete" and any(
        v is not None for v in (body.quality, body.mode, body.device_class)
    ):
        raise HTTPException(422, "Capture metadata is only accepted at completion")
    if body.action != "consent" and body.consent_version is not None:
        raise HTTPException(422, "Consent version is only accepted with consent")
    states = {
        "consent": "active",
        "complete": "completed",
        "interrupt": "interrupted",
        "cancel": "cancelled",
        "withdraw": "withdrawn",
    }
    event = {"action": body.action, "actor": u.id, "at": now()}
    payload = row.payload | {"events": row.payload["events"] + [event]}
    if body.action == "consent":
        payload |= {
            "participant_id": u.id,
            "consent": {"version": body.consent_version, **event},
        }
    if body.action == "complete":
        payload["capture"] = {
            "quality": body.quality,
            "mode": body.mode,
            "device_class": body.device_class,
            "recorded_at": event["at"],
        }
    row.payload = payload
    row.status = states[body.action]
    row.version += 1
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="research." + body.action,
            detail={"session_id": rid, "version": row.version},
        )
    )
    return receipt(db, u, cmd, h, pack(row))
