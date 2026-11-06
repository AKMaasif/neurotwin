"""Approved recurring activities, consented follow-up and explicit reminder delivery states."""

import datetime as dt
import hashlib
import json
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import (
    Audit,
    DeviceNotice,
    Grant,
    Outbox,
    Patient,
    Receipt,
    Record,
    Reminder,
    Routine,
    RoutineOccurrence,
    User,
    get_db,
    now,
)
from .security import authenticated, authorize

router = APIRouter(
    prefix="/api/patients/{pid}/routines", tags=["Routines and reminders"]
)
UTC = dt.timezone.utc


def utcnow():
    return dt.datetime.now(UTC)


def instant(value):
    return dt.datetime.fromisoformat(value)


def clock(value):
    return dt.time.fromisoformat(value)


def event(db, pid, actor, action, detail):
    db.add(Audit(patient_id=pid, actor=actor, action=action, detail=detail))


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Schedule(Input):
    timezone: str = Field(max_length=80)
    local_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start_date: dt.date
    end_date: dt.date

    @model_validator(mode="after")
    def valid(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid IANA time zone")
        if len(set(self.weekdays)) != len(self.weekdays) or any(
            d < 0 or d > 6 for d in self.weekdays
        ):
            raise ValueError("Choose unique weekdays from 0 to 6")
        if not 0 <= (self.end_date - self.start_date).days <= 365:
            raise ValueError("Use a date range of at most one year")
        return self


class Create(Schedule):
    template_id: str = Field(max_length=60)
    template_version: int = Field(ge=1)
    owner_id: str | None = Field(default=None, max_length=60)


class Edit(Schedule):
    expected_version: int = Field(ge=1)


class Consent(Input):
    expected_version: int = Field(ge=1)
    active: bool
    family_followup: bool = False
    recipient_id: str | None = Field(default=None, max_length=60)
    grace_minutes: int = Field(default=60, ge=15, le=1440)
    quiet_start: str = Field(default="21:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_end: str = Field(default="07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def valid(self):
        if self.family_followup and not self.recipient_id:
            raise ValueError("Choose a family contact for follow-up")
        if self.quiet_start == self.quiet_end:
            raise ValueError("Quiet hours need different start and end times")
        return self


class Action(Input):
    command_id: str = Field(min_length=8, max_length=100)
    task_version: int = Field(ge=1)
    routine_version: int = Field(ge=1)
    response: Literal["completed", "snooze", "help"]
    recipient_id: str | None = Field(default=None, max_length=60)
    snooze_minutes: int = Field(default=15, ge=5, le=120)


class NoticeAction(Input):
    expected_version: int = Field(ge=1)
    action: Literal["seen", "acknowledge"]


class DeviceAction(Input):
    expected_version: int = Field(ge=1)
    device_id: str = Field(pattern=r"^[a-zA-Z0-9-]{8,60}$")
    state: Literal["claim", "requested", "failed", "permission_denied", "clicked"] = (
        "claim"
    )


def resolve_wall(day, time, zone):
    naive = dt.datetime.combine(day, clock(time))
    tz = ZoneInfo(zone)
    for minute in range(181):
        local = naive + dt.timedelta(minutes=minute)
        aware = local.replace(tzinfo=tz, fold=0)
        utc = aware.astimezone(UTC)
        if utc.astimezone(tz).replace(tzinfo=None) == local:
            return (
                utc,
                "shifted_to_valid_minute"
                if minute
                else "earlier_fold"
                if aware.utcoffset() != local.replace(tzinfo=tz, fold=1).utcoffset()
                else "wall_time",
            )
    raise ValueError("Unresolvable wall time")


def outside_quiet(at, payload):
    tz = ZoneInfo(payload["timezone"])
    local = at.astimezone(tz)
    start = clock(payload.get("quiet_start", "21:00"))
    end = clock(payload.get("quiet_end", "07:00"))
    t = local.time().replace(tzinfo=None)
    quiet = start <= t < end if start < end else t >= start or t < end
    if not quiet:
        return at
    day = local.date() + dt.timedelta(days=1 if start > end and t >= start else 0)
    return resolve_wall(day, end.strftime("%H:%M"), payload["timezone"])[0]


def scoped(db, pid, rid):
    r = db.query(Routine).filter_by(patient_id=pid, id=rid).first()
    if not r:
        raise HTTPException(404, "Routine unavailable")
    return r


def check_owner(db, u, pid, r):
    authorize(db, u, pid, "respond")
    if u.role != "participant" or u.id != r.owner_id:
        raise HTTPException(403, "The participant must confirm this routine")


def family_contact(db, pid, owner_id, recipient_id):
    owner = db.get(User, owner_id)
    person = db.get(User, recipient_id) if recipient_id else None
    grant = (
        db.query(Grant)
        .filter_by(patient_id=pid, user_id=recipient_id, active=True)
        .first()
    )
    if (
        not owner
        or not person
        or person.role != "family"
        or person.org != owner.org
        or not grant
        or "help" not in grant.scopes
    ):
        raise HTTPException(403, "Choose a currently authorized family contact")
    return person


def source_valid(db, r):
    template = db.get(Record, r.template_id)
    plan = db.get(Record, r.payload["plan_id"])
    return (
        template
        and plan
        and plan.patient_id == r.patient_id
        and plan.kind == "plan"
        and plan.status == "approved"
        and not plan.payload.get("source_review_required")
        and plan.version == r.payload["plan_version"]
        and template.payload["title"] == r.payload["title"]
        and template.payload["steps"] == r.payload["steps"]
    )


def owner_valid(db, r):
    person = db.get(User, r.owner_id)
    patient = db.get(Patient, r.patient_id)
    grant = (
        db.query(Grant)
        .filter_by(patient_id=r.patient_id, user_id=r.owner_id, active=True)
        .first()
    )
    return (
        person
        and person.role == "participant"
        and person.org == patient.org
        and grant
        and "respond" in grant.scopes
    )


def cancel_notices(db, occ):
    for n in db.query(Reminder).filter_by(occurrence_id=occ.id):
        if n.state != "cancelled":
            n.state = "cancelled"
            n.version += 1


def close_help(db, occ, status, reason):
    h = db.get(Record, occ.help_id) if occ.help_id else None
    if h and h.status in ["requested", "accepted"]:
        h.status = status
        h.version += 1
        h.payload = h.payload | {"closed_reason": reason, "closed_at": now()}


def invalidate_occurrences(db, r):
    for occ in db.query(RoutineOccurrence).filter_by(routine_id=r.id):
        if occ.status in ["pending", "snoozed", "help"]:
            occ.status = "cancelled"
            task = db.get(Record, occ.task_id)
            task.status = "superseded"
            task.version += 1
            cancel_notices(db, occ)
            close_help(db, occ, "cancelled", "routine_changed")


def followup_allowed(db, r, occ, recipient):
    family_contact(db, r.patient_id, r.owner_id, recipient)
    h = db.get(Record, occ.help_id) if occ.help_id else None
    if (
        not h
        or h.status not in ["requested", "accepted"]
        or h.payload["recipient_id"] != recipient
    ):
        return False
    if not h.payload.get("automated_followup"):
        return True
    grant = (
        db.query(Grant)
        .filter_by(patient_id=r.patient_id, user_id=r.owner_id, active=True)
        .first()
    )
    return bool(
        r.payload.get("family_followup")
        and r.payload.get("recipient_id") == recipient
        and grant
        and {"help", "sharing"}.issubset(grant.scopes)
    )


def pack(r):
    return {
        "id": r.id,
        "version": r.version,
        "status": r.status,
        "owner_id": r.owner_id,
        "template_id": r.template_id,
        "payload": r.payload,
        "created_at": r.created_at,
    }


@router.get("")
def list_routines(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    authorize(db, u, pid, "summary")
    routines = (
        db.query(Routine)
        .filter_by(patient_id=pid)
        .order_by(Routine.created_at.desc())
        .all()
    )
    ids = [r.id for r in routines]
    occurrences = []
    viewer_grant = (
        db.query(Grant).filter_by(patient_id=pid, user_id=u.id, active=True).one()
    )
    routine_map = {r.id: r for r in routines}
    for o in (
        db.query(RoutineOccurrence)
        .filter(RoutineOccurrence.routine_id.in_(ids))
        .order_by(RoutineOccurrence.scheduled_at.desc())
        .limit(100)
    ):
        task = db.get(Record, o.task_id)
        h = db.get(Record, o.help_id) if o.help_id else None
        evidence = []
        if (
            u.id == routine_map[o.routine_id].owner_id
            or "review" in viewer_grant.scopes
        ):
            for item in db.query(Reminder).filter_by(occurrence_id=o.id):
                attempts = db.query(DeviceNotice).filter_by(reminder_id=item.id).all()
                evidence.append(
                    {
                        "kind": item.kind,
                        "state": item.state,
                        "seen": bool(item.seen_at),
                        "acknowledged": bool(item.acknowledged_at),
                        "device_states": sorted(set(a.state for a in attempts)),
                        "delivery_confirmed": False,
                    }
                )
        occurrences.append(
            {
                "id": o.id,
                "routine_id": o.routine_id,
                "routine_version": o.routine_version,
                "local_date": o.local_date,
                "scheduled_at": o.scheduled_at,
                "reminder_at": o.reminder_at,
                "status": o.status,
                "snoozes": o.snoozes,
                "resolution": o.resolution,
                "task": {
                    "id": task.id,
                    "version": task.version,
                    "status": task.status,
                    "title": task.payload["title"],
                },
                "help_id": o.help_id,
                "help_status": h.status if h else None,
                "reminder_evidence": evidence,
            }
        )
    notices = []
    for n in (
        db.query(Reminder)
        .join(RoutineOccurrence, RoutineOccurrence.id == Reminder.occurrence_id)
        .filter(
            RoutineOccurrence.routine_id.in_(ids),
            Reminder.recipient_id == u.id,
            Reminder.state != "cancelled",
        )
        .order_by(Reminder.created_at.desc())
        .limit(40)
    ):
        occ = db.get(RoutineOccurrence, n.occurrence_id)
        r = scoped(db, pid, occ.routine_id)
        if (
            r.status != "active"
            or not source_valid(db, r)
            or occ.status in ["cancelled", "expired", "completed", "skipped"]
        ):
            continue
        if not owner_valid(db, r):
            continue
        if n.kind == "family_followup":
            try:
                if not followup_allowed(db, r, occ, u.id):
                    continue
            except HTTPException:
                continue
        attempts = (
            db.query(DeviceNotice)
            .filter_by(reminder_id=n.id, reminder_version=n.version)
            .all()
        )
        notices.append(
            {
                "id": n.id,
                "occurrence_id": n.occurrence_id,
                "kind": n.kind,
                "state": n.state,
                "version": n.version,
                "seen_at": n.seen_at,
                "acknowledged_at": n.acknowledged_at,
                "device_states": sorted(set(a.state for a in attempts)),
                "device_allowed": outside_quiet(utcnow(), r.payload) <= utcnow(),
                "created_at": n.created_at,
            }
        )
    result = {
        "routines": [pack(r) for r in routines],
        "occurrences": occurrences,
        "reminders": notices,
        "server_time": utcnow().isoformat(),
        "delivery": "in_app_and_foreground_browser_only",
    }
    db.commit()
    return result


@router.post("")
def create(
    pid: str,
    body: Create,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    authorize(db, u, pid, "review" if u.role == "clinician" else "respond")
    if u.role not in ["participant", "clinician"]:
        raise HTTPException(403, "Participant or clinician required")
    owner_id = body.owner_id or u.id
    if u.role == "clinician" and not body.owner_id:
        owner_id = next(
            (
                user.id
                for user, g in db.query(User, Grant)
                .join(Grant, Grant.user_id == User.id)
                .filter(Grant.patient_id == pid, Grant.active.is_(True))
                if user.role == "participant" and "respond" in g.scopes
            ),
            None,
        )
    owner = db.get(User, owner_id) if owner_id else None
    grant = (
        db.query(Grant).filter_by(patient_id=pid, user_id=owner_id, active=True).first()
    )
    if (
        not owner
        or owner.role != "participant"
        or owner.org != u.org
        or not grant
        or "respond" not in grant.scopes
        or (u.role == "participant" and owner_id != u.id)
    ):
        raise HTTPException(403, "Participant assignment unavailable")
    template = db.get(Record, body.template_id)
    if (
        not template
        or template.patient_id != pid
        or template.kind != "task"
        or template.payload.get("occurrence_id")
    ):
        raise HTTPException(404, "Approved activity template unavailable")
    if template.version != body.template_version:
        raise HTTPException(409, "Activity changed; refresh")
    plan = db.get(Record, template.payload["plan_id"])
    if (
        not plan
        or plan.status != "approved"
        or plan.payload.get("source_review_required")
        or plan.version != template.payload["plan_version"]
    ):
        raise HTTPException(409, "Activity needs care-team review")
    if db.query(Routine).filter_by(patient_id=pid, template_id=template.id).first():
        raise HTTPException(
            409, "This activity already has a routine; edit or pause it"
        )
    if (
        db.query(Routine)
        .filter_by(patient_id=pid)
        .filter(Routine.status.in_(["active", "paused", "awaiting_consent"]))
        .count()
        >= 20
    ):
        raise HTTPException(422, "Routine limit reached")
    data = body.model_dump(
        mode="json", exclude={"template_id", "template_version", "owner_id"}
    ) | {
        "plan_id": plan.id,
        "plan_version": plan.version,
        "title": template.payload["title"],
        "steps": template.payload["steps"],
        "family_followup": False,
        "recipient_id": None,
        "grace_minutes": 60,
        "quiet_start": "21:00",
        "quiet_end": "07:00",
        "last_generated_date": None,
        "author_id": u.id,
        "activated_at": utcnow().isoformat() if u.role == "participant" else None,
    }
    r = Routine(
        patient_id=pid,
        owner_id=owner_id,
        template_id=template.id,
        status="active" if u.role == "participant" else "awaiting_consent",
        payload=data,
    )
    db.add(r)
    db.flush()
    if r.status == "active":
        template.payload = template.payload | {"is_routine_template": True}
        template.version += 1
    event(db, pid, u.id, "routine.created", {"routine_id": r.id, "status": r.status})
    db.commit()
    return pack(r)


@router.post("/{rid}/schedule")
def edit(
    pid: str,
    rid: str,
    body: Edit,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    authorize(db, u, pid, "review" if u.role == "clinician" else "respond")
    r = scoped(db, pid, rid)
    if u.role != "clinician":
        check_owner(db, u, pid, r)
    if r.version != body.expected_version:
        raise HTTPException(409, "Routine changed; refresh")
    invalidate_occurrences(db, r)
    r.version += 1
    r.payload = (
        r.payload
        | body.model_dump(mode="json", exclude={"expected_version"})
        | {"last_generated_date": None, "activated_at": utcnow().isoformat()}
    )
    if u.role == "clinician":
        r.status = "awaiting_consent"
        r.payload = r.payload | {
            "family_followup": False,
            "recipient_id": None,
            "activated_at": None,
        }
    event(
        db,
        pid,
        u.id,
        "routine.schedule_changed",
        {"routine_id": rid, "version": r.version},
    )
    db.commit()
    return pack(r)


@router.post("/{rid}/consent")
def consent(
    pid: str,
    rid: str,
    body: Consent,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    r = scoped(db, pid, rid)
    check_owner(db, u, pid, r)
    if r.version != body.expected_version:
        raise HTTPException(409, "Routine changed; refresh")
    if body.active and not source_valid(db, r):
        raise HTTPException(
            409, "The approved activity changed; ask your care team for review"
        )
    if body.family_followup:
        authorize(db, u, pid, "sharing")
        family_contact(db, pid, u.id, body.recipient_id)
    invalidate_occurrences(db, r)
    r.version += 1
    r.status = "active" if body.active else "paused"
    r.payload = (
        r.payload
        | body.model_dump(exclude={"expected_version", "active"})
        | {
            "recipient_id": body.recipient_id if body.family_followup else None,
            "activated_at": utcnow().isoformat() if body.active else None,
            "last_generated_date": None,
            "consented_at": utcnow().isoformat(),
        }
    )
    if body.active:
        template = db.get(Record, r.template_id)
        template.payload = template.payload | {"is_routine_template": True}
        template.version += 1
    event(
        db,
        pid,
        u.id,
        "routine.consent_changed",
        {
            "routine_id": rid,
            "active": body.active,
            "family_followup": body.family_followup,
        },
    )
    db.commit()
    return pack(r)


def notice(db, occ, recipient, kind):
    n = (
        db.query(Reminder)
        .filter_by(occurrence_id=occ.id, recipient_id=recipient, kind=kind)
        .first()
    )
    if not n:
        n = Reminder(occurrence_id=occ.id, recipient_id=recipient, kind=kind)
        db.add(n)
    elif n.state == "cancelled":
        n.state = "available_in_app"
        n.version += 1
        n.seen_at = None
        n.acknowledged_at = None
    return n


def request_help(db, r, occ, recipient, automated):
    family_contact(db, r.patient_id, r.owner_id, recipient)
    existing = db.get(Record, occ.help_id) if occ.help_id else None
    if existing and existing.status in ["requested", "accepted"]:
        existing_allowed = True
        try:
            family_contact(
                db, r.patient_id, r.owner_id, existing.payload["recipient_id"]
            )
        except HTTPException:
            existing_allowed = False
        if existing_allowed and (
            existing.payload["recipient_id"] == recipient or automated
        ):
            return existing
        close_help(db, occ, "cancelled", "participant_changed_contact")
        for prior in db.query(Reminder).filter_by(
            occurrence_id=occ.id, kind="family_followup"
        ):
            if prior.state != "cancelled":
                prior.state = "cancelled"
                prior.version += 1
    h = Record(
        patient_id=r.patient_id,
        kind="help",
        status="requested",
        payload={
            "text": (
                "This activity has not been confirmed. Please check in; non-confirmation does not establish a missed activity."
                if automated
                else "The participant asked for help with this approved activity."
            ),
            "sender_id": r.owner_id,
            "recipient_id": recipient,
            "routine_id": r.id,
            "occurrence_id": occ.id,
            "automated_followup": automated,
            "delivery": "saved_in_app",
            "clinical_use": False,
        },
    )
    db.add(h)
    db.flush()
    occ.help_id = h.id
    db.add(
        Outbox(
            patient_id=r.patient_id,
            event_type="routine.followup",
            payload={"record_id": h.id, "recipient_id": recipient},
        )
    )
    event(
        db,
        r.patient_id,
        r.owner_id,
        "routine.help_requested",
        {"occurrence_id": occ.id, "automated": automated},
    )
    notice(db, occ, recipient, "family_followup")
    return h


def tick(db, at=None):
    at = at or utcnow()
    changed = 0
    # Patient locks order scheduling against response, consent and grant revocation.
    patient_ids = [
        p[0]
        for p in db.query(Routine.patient_id).distinct().order_by(Routine.patient_id)
    ]
    for pid in patient_ids:
        db.execute(
            select(Patient).where(Patient.id == pid).with_for_update()
        ).scalar_one()
        for r in (
            db.query(Routine)
            .filter_by(patient_id=pid, status="active")
            .order_by(Routine.id)
        ):
            if not source_valid(db, r) or not owner_valid(db, r):
                invalidate_occurrences(db, r)
                r.status = "review_required"
                r.version += 1
                changed += 1
                continue
            tz = ZoneInfo(r.payload["timezone"])
            today = at.astimezone(tz).date()
            start = dt.date.fromisoformat(r.payload["start_date"])
            end = dt.date.fromisoformat(r.payload["end_date"])
            last = (
                dt.date.fromisoformat(r.payload["last_generated_date"])
                + dt.timedelta(days=1)
                if r.payload.get("last_generated_date")
                else start
            )
            first = max(start, last, today - dt.timedelta(days=6))
            day = first
            while day <= min(today, end):
                if day.weekday() in r.payload["weekdays"]:
                    o = (
                        db.query(RoutineOccurrence)
                        .filter_by(routine_id=r.id, local_date=day.isoformat())
                        .first()
                    )
                    if not o or o.status == "cancelled":
                        due, resolution = resolve_wall(
                            day, r.payload["local_time"], r.payload["timezone"]
                        )
                        initial = max(due, instant(r.payload["activated_at"]))
                        initial = outside_quiet(initial, r.payload)
                        if o:
                            task = db.get(Record, o.task_id)
                            task.status = "pending"
                            task.version += 1
                            o.status = "pending"
                            o.routine_version = r.version
                            o.scheduled_at = due.isoformat()
                            o.reminder_at = initial.isoformat()
                            o.snoozes = 0
                            o.help_id = None
                            o.resolution = resolution
                            task.payload = task.payload | {
                                "title": r.payload["title"],
                                "steps": r.payload["steps"],
                                "plan_id": r.payload["plan_id"],
                                "plan_version": r.payload["plan_version"],
                                "time": day.isoformat() + " " + r.payload["local_time"],
                            }
                        else:
                            task = Record(
                                patient_id=pid,
                                kind="task",
                                status="pending",
                                payload={
                                    "title": r.payload["title"],
                                    "steps": r.payload["steps"],
                                    "plan_id": r.payload["plan_id"],
                                    "plan_version": r.payload["plan_version"],
                                    "period": "scheduled",
                                    "time": day.isoformat()
                                    + " "
                                    + r.payload["local_time"],
                                    "evidence_type": None,
                                },
                            )
                            db.add(task)
                            db.flush()
                            o = RoutineOccurrence(
                                routine_id=r.id,
                                routine_version=r.version,
                                task_id=task.id,
                                local_date=day.isoformat(),
                                scheduled_at=due.isoformat(),
                                reminder_at=initial.isoformat(),
                                resolution=resolution,
                            )
                            db.add(o)
                            db.flush()
                            task.payload = task.payload | {
                                "occurrence_id": o.id,
                                "routine_id": r.id,
                            }
                        changed += 1
                day += dt.timedelta(days=1)
            if first <= min(today, end):
                r.payload = r.payload | {
                    "last_generated_date": min(today, end).isoformat()
                }
            for o in (
                db.query(RoutineOccurrence)
                .filter_by(routine_id=r.id)
                .filter(RoutineOccurrence.status.in_(["pending", "snoozed", "help"]))
            ):
                if at - instant(o.scheduled_at) > dt.timedelta(hours=24):
                    o.status = "expired"
                    task = db.get(Record, o.task_id)
                    task.status = "unconfirmed"
                    task.version += 1
                    cancel_notices(db, o)
                    close_help(
                        db, o, "closed_unconfirmed", "occurrence_expired_unconfirmed"
                    )
                    changed += 1
                    continue
                if instant(o.reminder_at) > at:
                    continue
                if outside_quiet(at, r.payload) > at:
                    continue
                notice(db, o, r.owner_id, "patient_reminder")
                if o.status == "snoozed":
                    o.status = "pending"
                if r.payload.get("family_followup") and at >= instant(
                    o.reminder_at
                ) + dt.timedelta(minutes=r.payload["grace_minutes"]):
                    try:
                        grant = (
                            db.query(Grant)
                            .filter_by(patient_id=pid, user_id=r.owner_id, active=True)
                            .first()
                        )
                        if not grant or not {"sharing", "help"}.issubset(grant.scopes):
                            continue
                        request_help(db, r, o, r.payload["recipient_id"], True)
                    except HTTPException:
                        continue
    db.flush()
    return changed


def validate_scheduled_task(db, task):
    if task.payload.get("is_routine_template"):
        raise HTTPException(409, "Use the dated activity for this routine")
    if not task.payload.get("occurrence_id"):
        return None
    occ = db.get(RoutineOccurrence, task.payload["occurrence_id"])
    r = db.get(Routine, occ.routine_id) if occ else None
    if (
        not r
        or r.status != "active"
        or r.version != occ.routine_version
        or occ.status in ["cancelled", "expired"]
        or utcnow() - instant(occ.scheduled_at) > dt.timedelta(hours=24)
        or not source_valid(db, r)
    ):
        raise HTTPException(
            409, "Scheduled activity changed; refresh before responding"
        )
    return occ


def sync_task_response(db, task, response, snooze_minutes=15):
    occ = validate_scheduled_task(db, task)
    if not occ:
        return
    r = db.get(Routine, occ.routine_id)
    if response == "deferred":
        if occ.snoozes >= 3:
            raise HTTPException(
                409,
                "This activity has already been postponed three times. Ask for help or review it.",
            )
        occ.status = "snoozed"
        occ.snoozes += 1
        occ.reminder_at = outside_quiet(
            utcnow() + dt.timedelta(minutes=snooze_minutes), r.payload
        ).isoformat()
        cancel_notices(db, occ)
        close_help(db, occ, "resolved", "participant_postponed")
    elif response in ["completed", "skipped"]:
        occ.status = response
        cancel_notices(db, occ)
        close_help(db, occ, "resolved", "participant_" + response)
    elif response == "help":
        occ.status = "help"
    elif response == "pending":
        occ.status = "pending"


@router.post("/occurrences/{oid}/response")
def respond(
    pid: str,
    oid: str,
    body: Action,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    authorize(db, u, pid, "respond")
    occ = db.get(RoutineOccurrence, oid)
    r = db.get(Routine, occ.routine_id) if occ else None
    if not r or r.patient_id != pid:
        raise HTTPException(404, "Scheduled activity unavailable")
    if u.id != r.owner_id:
        raise HTTPException(403, "Participant response required")
    command = body.model_dump() | {
        "patient_id": pid,
        "occurrence_id": oid,
        "operation": "routine_response",
    }
    hash_ = hashlib.sha256(json.dumps(command, sort_keys=True).encode()).hexdigest()
    old = db.query(Receipt).filter_by(actor=u.id, command_id=body.command_id).first()
    if old:
        if old.request_hash != hash_:
            raise HTTPException(409, "Command ID reused for different parameters")
        return old.result
    task = db.get(Record, occ.task_id)
    if task.version != body.task_version or r.version != body.routine_version:
        raise HTTPException(
            409, "Activity or routine changed. Review it before retrying."
        )
    validate_scheduled_task(db, task)
    if body.response == "help":
        authorize(db, u, pid, "help")
        request_help(db, r, occ, body.recipient_id, False)
    response = "deferred" if body.response == "snooze" else body.response
    sync_task_response(db, task, response, body.snooze_minutes)
    task.status = response
    task.version += 1
    task.payload = task.payload | {
        "evidence_type": "participant_statement",
        "responded_by": u.id,
        "responded_at": now(),
    }
    result = {
        "occurrence_id": oid,
        "status": occ.status,
        "task_version": task.version,
        "routine_version": r.version,
        "reminder_at": occ.reminder_at,
        "evidence": "participant report; not independently observed",
    }
    db.add(
        Receipt(
            actor=u.id, command_id=body.command_id, request_hash=hash_, result=result
        )
    )
    event(
        db,
        pid,
        u.id,
        "routine.response",
        {"occurrence_id": oid, "response": body.response},
    )
    db.commit()
    return result


def scoped_notice(db, u, pid, nid):
    authorize(db, u, pid, "summary")
    n = db.get(Reminder, nid)
    occ = db.get(RoutineOccurrence, n.occurrence_id) if n else None
    r = db.get(Routine, occ.routine_id) if occ else None
    if not n or not r or r.patient_id != pid or n.recipient_id != u.id:
        raise HTTPException(404, "Reminder unavailable")
    if (
        n.state == "cancelled"
        or r.status != "active"
        or not source_valid(db, r)
        or occ.status in ["cancelled", "expired", "completed", "skipped"]
        or utcnow() - instant(occ.scheduled_at) > dt.timedelta(hours=24)
    ):
        raise HTTPException(409, "Reminder is no longer active")
    if not owner_valid(db, r):
        raise HTTPException(403, "Participant grant no longer active")
    if n.kind == "family_followup" and not followup_allowed(db, r, occ, u.id):
        raise HTTPException(403, "Follow-up consent no longer active")
    return n


@router.post("/reminders/{nid}/acknowledge")
def acknowledge(
    pid: str,
    nid: str,
    body: NoticeAction,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    n = scoped_notice(db, u, pid, nid)
    if n.version != body.expected_version:
        raise HTTPException(409, "Reminder changed; refresh")
    if body.action == "seen" and n.state == "available_in_app":
        n.state = "seen_in_app"
        n.seen_at = now()
    if body.action == "acknowledge":
        n.state = "acknowledged"
        n.seen_at = n.seen_at or now()
        n.acknowledged_at = now()
    event(db, pid, u.id, "reminder." + body.action, {"reminder_id": nid})
    db.commit()
    return {
        "id": nid,
        "state": n.state,
        "version": n.version,
        "activity_completed": False,
    }


@router.post("/reminders/{nid}/device")
def device(
    pid: str,
    nid: str,
    body: DeviceAction,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    n = scoped_notice(db, u, pid, nid)
    if n.version != body.expected_version or n.state == "acknowledged":
        raise HTTPException(409, "Reminder changed or was acknowledged")
    attempt = (
        db.query(DeviceNotice)
        .filter_by(
            reminder_id=nid, device_id=body.device_id, reminder_version=n.version
        )
        .first()
    )
    if body.state == "claim":
        occ = db.get(RoutineOccurrence, n.occurrence_id)
        r = db.get(Routine, occ.routine_id)
        if outside_quiet(utcnow(), r.payload) > utcnow():
            raise HTTPException(409, "Quiet hours are active")
        if attempt:
            db.commit()
            return {"claimed": False, "state": attempt.state}
        attempt = DeviceNotice(
            reminder_id=nid, device_id=body.device_id, reminder_version=n.version
        )
        db.add(attempt)
        db.commit()
        return {"claimed": True, "state": "claimed", "attempt_id": attempt.id}
    if not attempt:
        raise HTTPException(409, "Claim the notification first")
    if attempt.state == "claimed" or (
        body.state == "clicked" and attempt.state == "requested"
    ):
        attempt.state = body.state
    event(
        db,
        pid,
        u.id,
        "reminder.device_state",
        {"reminder_id": nid, "state": attempt.state},
    )
    db.commit()
    return {"state": attempt.state, "delivery_confirmed": False}
