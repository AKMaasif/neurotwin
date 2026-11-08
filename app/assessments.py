"""Versioned assessment delivery, bounded evidence capture and human review."""

import copy
import datetime as dt
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy.orm import Session

from .assessment_protocol import (
    PROTOCOL,
    orientation,
    public_step,
    score_session,
    steps,
    validate_response,
)
from .db import Audit, Record, User, get_db, now
from .security import authenticated, authorize


class AssessmentRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def redacted(request):
            try:
                return await original(request)
            except RequestValidationError:
                raise HTTPException(
                    422,
                    "Invalid assessment request; check the required fields and permitted values",
                ) from None

        return redacted


router = APIRouter(
    prefix="/api/patients/{pid}/assessments", route_class=AssessmentRoute
)


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    command_id: str = Field(min_length=8, max_length=100)


class Assignment(Command):
    protocol_version: Literal["1.0"]
    timezone: str = Field(default="Asia/Dubai", min_length=1, max_length=60)
    location: str = Field(min_length=2, max_length=80)
    acknowledge_adaptation: Literal[True]


class Versioned(Command):
    expected_version: int = Field(ge=1)


class Consent(Versioned):
    consent_version: Literal["assessment-research-1"]
    understands_english: Literal[True]
    comfortable_reading: Literal[True]
    mode: Literal["self", "assisted", "video"]
    device_class: Literal["phone", "tablet", "desktop"]


class Answer(Versioned):
    step_id: str = Field(min_length=1, max_length=40)
    values: list[str] = Field(max_length=100)
    attempts: list[list[str]] = Field(default_factory=list, max_length=15)
    client_elapsed_ms: int = Field(ge=0, le=900000)
    corrected: StrictBool = False
    difficulty: Literal[
        "none", "vision", "hearing", "motor", "understanding", "other"
    ] = "none"


class Transition(Versioned):
    action: Literal["complete", "interrupt", "cancel", "withdraw"]
    quality: Literal["usable", "poor"] | None = None


class Review(Versioned):
    outcome: Literal["reviewed_research", "invalid"]
    rationale: str = Field(min_length=12, max_length=2000)
    participant_note: str = Field(min_length=12, max_length=500)
    item_points: dict[str, StrictInt | None]
    checked_evidence: Literal[True]


def access(db, actor, pid):
    patient = authorize(db, actor, pid, "assessment")
    if actor.role not in {"participant", "clinician"} or not patient.synthetic:
        raise HTTPException(
            403,
            "Assessment adaptation is available only in synthetic research workspaces",
        )
    return patient


def clinician(db, actor, pid):
    authorize(db, actor, pid, "review")
    if actor.role != "clinician":
        raise HTTPException(403, "Clinician action required")


def projected(row, actor):
    from .main import pack

    if actor.role == "clinician":
        return pack(row)
    p = row.payload
    # No answer keys, orientation reference, previous answers, scores or private review.
    safe = {k: p[k] for k in ("protocol", "assigned_by", "participant_id", "events")}
    safe["progress"] = dict(completed=len(p["responses"]), total=len(p["steps"]))
    safe["step_started_at"] = p.get("step_started_at")
    safe["expired"] = expired(p)
    if row.status == "active" and len(p["responses"]) < len(p["steps"]):
        safe["current_step"] = public_step(p["steps"][len(p["responses"])])
    if row.status == "reviewed":
        safe["review_note"] = p["review"]["participant_note"]
    return dict(
        id=row.id,
        kind=row.kind,
        version=row.version,
        status=row.status,
        created_at=row.created_at,
        payload=safe,
    )


def expired(payload):
    start = payload.get("started_at")
    return bool(
        start
        and (
            dt.datetime.fromisoformat(now()) - dt.datetime.fromisoformat(start)
        ).total_seconds()
        > PROTOCOL["time_limit_seconds"]
    )


def prepare(db, u, pid, rid, body, operation):
    from .main import replay, scoped_record

    access(db, u, pid)
    row = scoped_record(db, pid, rid, "assessment_session")
    if u.role == "participant" and row.payload["participant_id"] not in (None, u.id):
        raise HTTPException(403, "This session belongs to another participant")
    if operation == "review":
        clinician(db, u, pid)
    elif u.role != "participant" and operation != "cancel":
        raise HTTPException(
            403, "Participant action required; proxy consent is unavailable"
        )
    elif u.role == "clinician":
        clinician(db, u, pid)
    cmd = body.model_dump() | dict(
        patient_id=pid, session_id=rid, operation="assessment." + operation
    )
    h, previous = replay(db, u, cmd)
    if previous is not None:
        # A historical receipt must not resurrect answers or a withdrawn result.
        if row.status == "withdrawn" and operation != "withdraw":
            raise HTTPException(409, "Consent was withdrawn")
        return row, cmd, h, projected(row, u)
    if row.version != body.expected_version:
        raise HTTPException(409, "Session changed; refresh before continuing")
    if (
        operation not in {"withdraw", "interrupt", "cancel"}
        and row.payload["protocol"] != PROTOCOL
    ):
        raise HTTPException(409, "Protocol changed; request a new assignment")
    if operation not in {"withdraw", "interrupt", "cancel", "consent"} and (
        not row.payload.get("reference")
        or row.payload["steps"] != steps(row.payload["reference"])
    ):
        raise HTTPException(409, "Activity snapshot changed; request a new assignment")
    return row, cmd, h, None


def saved(db, u, row, cmd, h, payload, status=None):
    from .main import receipt

    event = dict(action=cmd["operation"].split(".")[-1], actor=u.id, at=now())
    payload["events"] = payload["events"] + [event]
    row.payload = payload
    row.version += 1
    if status:
        row.status = status
    db.add(
        Audit(
            patient_id=row.patient_id,
            actor=u.id,
            action=cmd["operation"],
            detail=dict(session_id=row.id, version=row.version),
        )
    )
    # Keep receipts free of clinical evidence; prepare() projects the current row.
    receipt(db, u, cmd, h, dict(id=row.id, version=row.version, status=row.status))
    return projected(row, u)


@router.get("")
def sessions(pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    access(db, u, pid)
    if u.role == "clinician":
        clinician(db, u, pid)
    rows = (
        db.query(Record)
        .filter_by(patient_id=pid, kind="assessment_session")
        .order_by(Record.created_at.desc(), Record.id)
        .all()
    )
    rows = [
        r
        for r in rows
        if u.role == "clinician" or r.payload["participant_id"] in (None, u.id)
    ]
    db.add(Audit(patient_id=pid, actor=u.id, action="assessment.read", detail={}))
    db.commit()
    return dict(protocol=PROTOCOL, sessions=[projected(r, u) for r in rows])


@router.post("")
def assign(
    pid: str,
    body: Assignment,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    from .main import receipt, replay, scoped_record

    access(db, u, pid)
    clinician(db, u, pid)
    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Use a recognized IANA timezone") from None
    cmd = body.model_dump() | dict(patient_id=pid, operation="assessment.assign")
    h, previous = replay(db, u, cmd)
    if previous is not None:
        return projected(
            scoped_record(db, pid, previous["id"], "assessment_session"), u
        )
    if (
        db.query(Record)
        .filter(
            Record.patient_id == pid,
            Record.kind == "assessment_session",
            Record.status.in_(["awaiting_consent", "active", "awaiting_review"]),
        )
        .first()
    ):
        raise HTTPException(
            409, "An assessment already awaits consent, completion or review"
        )
    row = Record(
        patient_id=pid,
        kind="assessment_session",
        status="awaiting_consent",
        payload=dict(
            protocol=copy.deepcopy(PROTOCOL),
            assigned_by=u.id,
            participant_id=None,
            assignment=dict(timezone=body.timezone, location=body.location),
            steps=[],
            responses=[],
            events=[],
            clinical_use=False,
        ),
    )
    db.add(row)
    db.flush()
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="assessment.assign",
            detail=dict(session_id=row.id),
        )
    )
    receipt(db, u, cmd, h, dict(id=row.id))
    return projected(row, u)


@router.post("/{rid}/consent")
def consent(
    pid: str,
    rid: str,
    body: Consent,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row, cmd, h, previous = prepare(db, u, pid, rid, body, "consent")
    if previous is not None:
        return previous
    if row.status != "awaiting_consent":
        raise HTTPException(409, "Consent is unavailable in this state")
    p = copy.deepcopy(row.payload)
    at = now()
    ref = orientation(**p["assignment"], at=at)
    p.update(
        participant_id=u.id,
        started_at=at,
        reference=ref,
        steps=steps(ref),
        consent=body.model_dump(exclude={"command_id", "expected_version"})
        | dict(actor=u.id, at=at),
    )
    return saved(db, u, row, cmd, h, p, "active")


@router.post("/{rid}/begin")
def begin(
    pid: str,
    rid: str,
    body: Versioned,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row, cmd, h, previous = prepare(db, u, pid, rid, body, "begin")
    if previous is not None:
        return previous
    p = copy.deepcopy(row.payload)
    if (
        row.status != "active"
        or len(p["responses"]) == len(p["steps"])
        or p.get("step_started_at")
    ):
        raise HTTPException(
            409,
            "Activity is unavailable or already started; do not restart a timed activity",
        )
    if expired(p):
        p["score"] = score_session(p)
        return saved(db, u, row, cmd, h, p, "interrupted")
    p["step_started_at"] = now()
    return saved(db, u, row, cmd, h, p)


@router.post("/{rid}/answer")
def answer(
    pid: str,
    rid: str,
    body: Answer,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row, cmd, h, previous = prepare(db, u, pid, rid, body, "answer")
    if previous is not None:
        return previous
    p = copy.deepcopy(row.payload)
    if (
        row.status != "active"
        or not p.get("step_started_at")
        or len(p["responses"]) >= len(p["steps"])
    ):
        raise HTTPException(409, "Start the next activity before saving an answer")
    if expired(p):
        p["score"] = score_session(p)
        return saved(db, u, row, cmd, h, p, "interrupted")
    step = p["steps"][len(p["responses"])]
    if step["id"] != body.step_id:
        raise HTTPException(409, "Only the current activity can be answered")
    if any(len(s) > 100 for s in body.values) or any(
        len(trial) > 60 or any(len(s) > 10 for s in trial) for trial in body.attempts
    ):
        raise HTTPException(422, "Response evidence exceeds its allowed size")
    try:
        validate_response(step, body.values, body.attempts)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    elapsed = max(
        0,
        int(
            (
                dt.datetime.fromisoformat(now())
                - dt.datetime.fromisoformat(p["step_started_at"])
            ).total_seconds()
            * 1000
        ),
    )
    if step["kind"] == "learning" and body.values and elapsed < 15000:
        raise HTTPException(409, "The word presentation has not finished")
    p["responses"].append(
        body.model_dump(exclude={"command_id", "expected_version"})
        | dict(
            started_at=p["step_started_at"],
            received_at=now(),
            server_elapsed_ms=elapsed,
        )
    )
    p["step_started_at"] = None
    return saved(db, u, row, cmd, h, p)


@router.post("/{rid}/transition")
def transition(
    pid: str,
    rid: str,
    body: Transition,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row, cmd, h, previous = prepare(db, u, pid, rid, body, body.action)
    if previous is not None:
        return previous
    allowed = dict(
        complete={"active"},
        interrupt={"active"},
        cancel={"awaiting_consent"},
        withdraw={"active", "awaiting_review", "interrupted", "reviewed"},
    )
    if row.status not in allowed[body.action]:
        raise HTTPException(409, "Action unavailable in the current state")
    if (body.action == "complete") != (body.quality is not None):
        raise HTTPException(422, "Quality is required only when finishing")
    p = copy.deepcopy(row.payload)
    status = dict(
        complete="awaiting_review",
        interrupt="interrupted",
        cancel="cancelled",
        withdraw="withdrawn",
    )[body.action]
    if body.action == "complete":
        if len(p["responses"]) != len(p["steps"]):
            raise HTTPException(409, "Complete or explicitly skip every activity first")
        p["quality"] = body.quality
        if expired(p):
            status = "interrupted"
    if body.action in {"complete", "interrupt"}:
        p["score"] = score_session(p)
    if body.action == "withdraw":
        p.pop("review", None)
        p.pop("score", None)
    return saved(db, u, row, cmd, h, p, status)


@router.post("/{rid}/review")
def review(
    pid: str,
    rid: str,
    body: Review,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    row, cmd, h, previous = prepare(db, u, pid, rid, body, "review")
    if previous is not None:
        return previous
    if row.status not in {"awaiting_review", "interrupted"}:
        raise HTTPException(409, "A completed or interrupted session is required")
    p = copy.deepcopy(row.payload)
    score = score_session(p)
    if set(body.item_points) != {i["id"] for i in score["items"]}:
        raise HTTPException(422, "Review every scored item, including missing items")
    for item in score["items"]:
        value = body.item_points[item["id"]]
        if (
            value is not None
            and (isinstance(value, bool) or not 0 <= value <= item["maximum"])
        ) or (item["points"] is None and value is not None):
            raise HTTPException(
                422,
                "Missing evidence cannot be assigned points; use each item's allowed range",
            )
    flagged = (
        p.get("quality") != "usable"
        or p["consent"]["mode"] != "self"
        or any(r["difficulty"] != "none" or not r["values"] for r in p["responses"])
    )
    if body.outcome == "reviewed_research" and (
        row.status == "interrupted" or not score["complete"] or flagged
    ):
        raise HTTPException(
            409, "Incomplete, assisted or poor-quality evidence must be marked invalid"
        )
    points = list(body.item_points.values())
    if body.outcome == "reviewed_research" and any(v is None for v in points):
        raise HTTPException(422, "A reviewed result requires a decision for every item")
    p["review"] = body.model_dump(exclude={"command_id", "expected_version"}) | dict(
        actor=u.id,
        at=now(),
        total=sum(points)
        if body.outcome == "reviewed_research" and all(v is not None for v in points)
        else None,
        clinical_use=False,
    )
    return saved(db, u, row, cmd, h, p, "reviewed")
