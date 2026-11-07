"""Authenticated software-only device events; never physical telemetry."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .db import Audit, Grant, Record, User, get_db, now
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/iot-simulation")
CONSENT_VERSION = "iot-simulation-1"
CONSENT_TEXT = (
    "Allow your authorized clinician to inject clearly labelled device test events "
    "into this synthetic workspace. No physical device, location or medical measurement "
    "is collected. Test events and manual review decisions are stored for software "
    "demonstration only. You can withdraw this permission; stored events and audit "
    "records are retained. No emergency dispatch or clinical recommendation is generated."
)


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=8, max_length=100)
    expected_version: int = Field(ge=1)


class Permission(Command):
    expected_version: int = Field(ge=0)
    enabled: bool = Field(strict=True)
    consent_version: str | None = Field(default=None, max_length=80)


class Event(Command):
    sequence: int = Field(ge=1, le=1_000_000_000, strict=True)
    occurred_at: AwareDatetime
    kind: Literal[
        "connected",
        "disconnected",
        "reading",
        "missing_reading",
        "fault",
        "review_signal",
    ]
    value: int | None = Field(default=None, ge=0, le=1_000_000, strict=True)


class Review(Command):
    decision: Literal["acknowledged", "rejected"]


def access(db, actor, pid, clinician=False):
    patient = authorize(db, actor, pid, "assessment")
    if not patient.synthetic or actor.role not in {"participant", "clinician"}:
        raise HTTPException(
            403, "Device simulation is restricted to synthetic workspaces"
        )
    if clinician:
        authorize(db, actor, pid, "review")
        if actor.role != "clinician":
            raise HTTPException(403, "Clinician simulation access required")


def state_record(db, pid):
    return (
        db.query(Record).filter_by(patient_id=pid, kind="iot_simulation").one_or_none()
    )


def save(db, actor, pid, command, request_hash, result, action, detail):
    from .main import receipt

    db.add(
        Audit(
            patient_id=pid,
            actor=actor.id,
            action="iot.simulation." + action,
            detail=detail,
        )
    )
    return receipt(db, actor, command, request_hash, result)


@router.get("")
def read(
    pid: str,
    offset: int = Query(default=0, ge=0),
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import pack

    access(db, u, pid)
    state = state_record(db, pid)
    events = db.query(Record).filter_by(patient_id=pid, kind="iot_sim_event")
    total = events.count()
    result = {
        "state": pack(state) if state else None,
        "consent_version": CONSENT_VERSION,
        "consent_text": CONSENT_TEXT,
        "events": [
            pack(row)
            for row in events.order_by(Record.created_at.desc(), Record.id.desc())
            .offset(offset)
            .limit(50)
        ],
        "offset": offset,
        "total": total,
        "simulated": True,
        "clinical_use": False,
    }
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="iot.simulation.read",
            detail={"offset": offset},
        )
    )
    db.commit()
    return result


@router.post("/permission")
def permission(
    pid: str,
    body: Permission,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import pack, replay

    access(db, u, pid)
    if u.role != "participant":
        raise HTTPException(
            403, "Only the participant can change simulation permission"
        )
    state = state_record(db, pid)
    if state and state.payload["participant_id"] != u.id:
        raise HTTPException(403, "Permission belongs to another participant")
    cmd = body.model_dump() | {"patient_id": pid, "operation": "iot.permission"}
    h, previous = replay(db, u, cmd)
    if previous is not None:
        return previous
    if body.expected_version != (state.version if state else 0):
        raise HTTPException(409, "Simulation permission changed; refresh first")
    if body.enabled and body.consent_version != CONSENT_VERSION:
        raise HTTPException(
            409, "Current simulation consent must be accepted explicitly"
        )
    if not body.enabled and (not state or body.consent_version is not None):
        raise HTTPException(
            422, "Withdrawal requires existing permission and no new consent"
        )
    if state and (state.status == "enabled") == body.enabled:
        raise HTTPException(409, "Permission is already in the requested state")
    if not state:
        state = Record(
            patient_id=pid,
            kind="iot_simulation",
            status="enabled",
            payload={
                "sequence": 0,
                "participant_id": u.id,
                "simulated": True,
                "source_type": "simulated_device",
                "clinical_use": False,
            },
        )
        db.add(state)
        db.flush()
    else:
        state.version += 1
    state.status = "enabled" if body.enabled else "withdrawn"
    state.payload = state.payload | {
        "connection": "unknown",
        "permission": {
            "enabled": body.enabled,
            "consent_version": CONSENT_VERSION,
            "consent_text": CONSENT_TEXT,
            "actor": u.id,
            "at": now(),
            "version": state.version,
        },
    }
    return save(
        db,
        u,
        pid,
        cmd,
        h,
        pack(state),
        "permission",
        {
            "state_id": state.id,
            "version": state.version,
            "enabled": body.enabled,
            "consent_version": CONSENT_VERSION,
            "consent_text": CONSENT_TEXT,
        },
    )


@router.post("/events")
def event(
    pid: str,
    body: Event,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import pack, replay

    access(db, u, pid, clinician=True)
    state = state_record(db, pid)
    if not state or state.status != "enabled":
        raise HTTPException(409, "Participant simulation permission is not active")
    if state.payload["permission"]["consent_version"] != CONSENT_VERSION:
        raise HTTPException(409, "Updated participant consent is required")
    participant_grant = (
        db.query(Grant)
        .filter_by(user_id=state.payload["participant_id"], patient_id=pid, active=True)
        .one_or_none()
    )
    if not participant_grant or "assessment" not in participant_grant.scopes:
        raise HTTPException(409, "Participant simulation access is no longer active")
    cmd = body.model_dump(mode="json") | {"patient_id": pid, "operation": "iot.event"}
    h, previous = replay(db, u, cmd)
    if previous is not None:
        return previous
    if state.version != body.expected_version:
        raise HTTPException(409, "Simulation changed; refresh before injecting")
    if body.sequence <= state.payload["sequence"]:
        raise HTTPException(409, "Event sequence must increase")
    timestamp = body.occurred_at.astimezone(dt.timezone.utc)
    if timestamp > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise HTTPException(422, "Event timestamp is too far in the future")
    last = state.payload.get("last_occurred_at")
    if last and timestamp < dt.datetime.fromisoformat(last):
        raise HTTPException(409, "Event timestamp precedes the accepted stream")
    if (body.kind == "reading") != (body.value is not None):
        raise HTTPException(422, "Only a reading requires an activity count")
    if body.kind == "reading" and state.payload["connection"] != "connected":
        raise HTTPException(409, "Readings require an explicitly connected simulation")
    gap = body.sequence - state.payload["sequence"] - 1
    row = Record(
        patient_id=pid,
        kind="iot_sim_event",
        status="awaiting_review" if body.kind == "review_signal" else "recorded",
        payload={
            "kind": body.kind,
            "sequence": body.sequence,
            "sequence_gap": gap,
            "occurred_at": timestamp.isoformat(),
            "received_at": now(),
            "value": body.value,
            "metric": "activity_count" if body.kind == "reading" else None,
            "unit": "count" if body.kind == "reading" else None,
            "simulated": True,
            "source_type": "simulated_device",
            "clinical_use": False,
            "injected_by": u.id,
            "permission_version": state.payload["permission"]["version"],
            "consent_version": state.payload["permission"]["consent_version"],
        },
    )
    db.add(row)
    db.flush()
    connection = {
        "connected": "connected",
        "disconnected": "disconnected",
        "fault": "faulted",
    }.get(body.kind, state.payload["connection"])
    state.payload = state.payload | {
        "sequence": body.sequence,
        "connection": connection,
        "last_occurred_at": timestamp.isoformat(),
    }
    state.version += 1
    return save(
        db,
        u,
        pid,
        cmd,
        h,
        {"state": pack(state), "event": pack(row)},
        "injected",
        {"event_id": row.id, "kind": body.kind, "sequence_gap": gap},
    )


@router.post("/events/{rid}/review")
def review(
    pid: str,
    rid: str,
    body: Review,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import pack, replay, scoped_record

    access(db, u, pid, clinician=True)
    row = scoped_record(db, pid, rid, "iot_sim_event")
    cmd = body.model_dump() | {
        "patient_id": pid,
        "event_id": rid,
        "operation": "iot.review",
    }
    h, previous = replay(db, u, cmd)
    if previous is not None:
        return previous
    if row.version != body.expected_version or row.status != "awaiting_review":
        raise HTTPException(409, "Review signal changed or is already reviewed")
    row.payload = row.payload | {
        "review": {"decision": body.decision, "actor": u.id, "at": now()}
    }
    row.status = "reviewed"
    row.version += 1
    return save(
        db,
        u,
        pid,
        cmd,
        h,
        pack(row),
        "reviewed",
        {"event_id": rid, "decision": body.decision},
    )
