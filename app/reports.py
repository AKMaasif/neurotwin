"""Dated activity projections and human-reviewed, recipient-bound snapshots."""

import datetime as dt
import hashlib
import json
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .ai import ProviderUnavailable, gateway
from .config import settings
from .db import Audit, Grant, Record, RoutineOccurrence, User, get_db, now
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/reports", tags=["reports"])
STATES = (
    "completed",
    "deferred",
    "skipped",
    "help",
    "pending",
    "unconfirmed",
    "unknown",
)
EVENTS = {"task.response", "routine.response", "help.requested", "help.accepted"}
LIMIT = 10000


def timestamp(value):
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def zone(value):
    try:
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise HTTPException(422, "Choose a valid IANA timezone") from None


def selection(end_date, timezone):
    tz = zone(timezone)
    today = timestamp(now()).astimezone(tz).date()
    end = end_date or today
    if end > today or end < dt.date(2000, 1, 28):
        raise HTTPException(
            422, "Choose a past or current reporting date after January 2000"
        )
    return end, tz


def clinician(db, u, pid):
    authorize(db, u, pid, "review")
    if u.role != "clinician":
        raise HTTPException(403, "Assigned clinician required")


def viewer(db, u, pid, audience, recipient_id=None):
    authorize(db, u, pid, "summary")
    if audience == "clinical":
        clinician(db, u, pid)
        if recipient_id and recipient_id != u.id:
            raise HTTPException(
                422, "Clinical snapshots belong to the reviewing clinician"
            )
        return u
    if recipient_id == u.id and u.role == "clinician":
        raise HTTPException(422, "Choose a family recipient for a family snapshot")
    if recipient_id and recipient_id != u.id:
        clinician(db, u, pid)
        target = db.get(User, recipient_id)
        if not target or target.role != "family":
            raise HTTPException(403, "Choose an authorized family recipient")
        authorize(db, target, pid, "summary")
        return target
    return u


def project(db, pid, actor, end, tz, audience):
    """Latest recorded states of dated cohorts, never an as-of-week-close estimate.

    Family queries deliberately exclude clinical, document and companion records.
    Fail closed rather than return a silently incomplete projection at the row cap.
    """
    kinds = ["task", "plan", "help"]
    if audience == "clinical":
        kinds += ["observation", "case", "document"]
    source = (
        db.query(Record)
        .filter(Record.patient_id == pid, Record.kind.in_(kinds))
        .order_by(Record.id)
        .limit(LIMIT + 1)
        .all()
    )
    if len(source) > LIMIT:
        raise HTTPException(
            422, "Reporting source limit reached; use a partitioned reporting service"
        )
    grant = (
        db.query(Grant).filter_by(user_id=actor.id, patient_id=pid, active=True).one()
    )
    scopes = grant.scopes
    by_id = {r.id: r for r in source}
    plans = {
        r.id: r
        for r in source
        if r.kind == "plan"
        and (
            r.status == "approved"
            or (r.status == "superseded" and r.payload.get("signed_by"))
        )
    }
    # Occurrences have no patient column; join through their patient-bound task.
    occurrences = (
        db.query(RoutineOccurrence)
        .join(Record, Record.id == RoutineOccurrence.task_id)
        .filter(Record.patient_id == pid)
        .limit(LIMIT + 1)
        .all()
    )
    if len(occurrences) > LIMIT:
        raise HTTPException(422, "Reporting occurrence limit reached")
    scheduled = {o.task_id: o for o in occurrences}
    occ_tasks = {o.id: o.task_id for o in occurrences}
    first = end - dt.timedelta(days=27)
    week_start = end - dt.timedelta(days=6)
    days = {first + dt.timedelta(days=i): {s: 0 for s in STATES} for i in range(28)}
    excluded = {d: 0 for d in days}
    cohort = []
    invalid_dates = 0
    for r in source:
        if (
            r.kind != "task"
            or "tasks" not in scopes
            or r.payload.get("is_routine_template")
        ):
            continue
        if r.payload.get("plan_id") not in plans:
            continue
        event_time = timestamp(
            scheduled[r.id].scheduled_at if r.id in scheduled else r.created_at
        )
        if not event_time:
            invalid_dates += 1
            continue
        if r.id in scheduled and event_time > timestamp(now()):
            continue
        day = event_time.astimezone(tz).date()
        if day not in days:
            continue
        if r.status in {"cancelled", "superseded"}:
            excluded[day] += 1
            continue
        state = r.status if r.status in STATES else "unknown"
        days[day][state] += 1
        if day >= week_start:
            cohort.append(
                {
                    "id": r.id,
                    "version": r.version,
                    "plan_version": plans[r.payload["plan_id"]].version,
                    "source_review_required": bool(
                        plans[r.payload["plan_id"]].payload.get(
                            "source_review_required"
                        )
                    ),
                    "date": day.isoformat(),
                    "title": r.payload.get("title", "Activity"),
                    "status": state,
                    "date_basis": "scheduled" if r.id in scheduled else "created",
                }
            )
    daily = [
        {
            "date": d.isoformat(),
            "counts": days[d],
            "denominator": sum(days[d].values()),
            "excluded": excluded[d],
        }
        for d in days
        if d >= week_start
    ]
    trend = []
    for i in range(4):
        a = first + dt.timedelta(days=7 * i)
        b = a + dt.timedelta(days=6)
        counts = {
            s: sum(days[a + dt.timedelta(days=j)][s] for j in range(7)) for s in STATES
        }
        trend.append(
            {
                "start": a.isoformat(),
                "end": b.isoformat(),
                "counts": counts,
                "denominator": sum(counts.values()),
            }
        )
    helpers = {
        r.id: r
        for r in source
        if r.kind == "help"
        and "help" in scopes
        and (
            audience == "clinical"
            or actor.id in (r.payload.get("sender_id"), r.payload.get("recipient_id"))
        )
    }
    # ISO timestamps are normalized to UTC by this application. A broad date
    # filter plus aware parsing keeps offsets and boundary dates correct.
    lower = dt.datetime.combine(week_start, dt.time.min, tzinfo=tz).astimezone(
        dt.timezone.utc
    )
    upper = dt.datetime.combine(
        end + dt.timedelta(days=1), dt.time.min, tzinfo=tz
    ).astimezone(dt.timezone.utc)
    events = (
        db.query(Audit)
        .filter(
            Audit.patient_id == pid,
            Audit.action.in_(EVENTS),
            Audit.created_at >= (lower - dt.timedelta(days=1)).isoformat(),
            Audit.created_at < (upper + dt.timedelta(days=1)).isoformat(),
        )
        .order_by(Audit.created_at, Audit.id)
        .limit(LIMIT + 1)
        .all()
    )
    if len(events) > LIMIT:
        raise HTTPException(422, "Reporting event limit reached")
    timeline = []
    for event in events:
        when = timestamp(event.created_at)
        if not when or not lower <= when < upper:
            continue
        rid = event.detail.get("record") or occ_tasks.get(
            event.detail.get("occurrence_id")
        )
        r = by_id.get(rid)
        if event.action.startswith("help."):
            if rid not in helpers:
                continue
        elif (
            not r
            or r.kind != "task"
            or "tasks" not in scopes
            or r.payload.get("plan_id") not in plans
        ):
            continue
        timeline.append(
            {
                "id": event.id,
                "at": event.created_at,
                "action": event.action,
                "source_id": rid,
                "response": event.detail.get("response"),
                "title": r.payload.get("title", "Support request")
                if r
                else "Support request",
            }
        )
    counts = trend[-1]["counts"]
    facts = [
        {
            "id": f"count:{s}",
            "text": f"{counts[s]} of {trend[-1]['denominator']} recorded activities have latest state {s}.",
        }
        for s in STATES
    ]
    facts.append(
        {
            "id": "coverage",
            "text": f"{sum(d['denominator'] > 0 for d in daily)} of 7 dates have recorded activities. Dates without records do not establish missed activities.",
        }
    )
    clinical = None
    if audience == "clinical":
        measurements = []
        sources = []
        for r in source:
            created = timestamp(r.created_at)
            if r.kind == "observation" and created and lower <= created < upper:
                measurements.append(
                    {
                        "source_id": r.id,
                        "quality": r.status,
                        "protocol": r.payload.get("protocol"),
                        "mode": r.payload.get("mode"),
                        "value": r.payload.get("value"),
                        "clinical_use": False,
                    }
                )
            if r.kind == "document":
                for fact in r.payload.get("candidates", []):
                    reviewed = timestamp(fact.get("reviewed_at"))
                    if (
                        fact.get("status") == "verified"
                        and reviewed
                        and lower <= reviewed < upper
                    ):
                        sources.append(
                            {
                                "source_id": r.id,
                                "version": r.version,
                                "fact_id": fact.get("id"),
                                "label": fact.get("label"),
                                "quote": fact.get("quote"),
                                "source_refs": fact.get("source_refs", []),
                                "reviewed_at": fact.get("reviewed_at"),
                            }
                        )
        clinical = {
            "research_measurements": measurements,
            "verified_source_facts": sources,
            "review_items": [
                {
                    "source_id": r.id,
                    "status": r.status,
                    "concern": r.payload.get("concern"),
                }
                for r in source
                if r.kind == "case"
                and r.status in {"awaiting_review", "information_requested"}
            ],
            "plans_requiring_source_review": [
                r.id for r in plans.values() if r.payload.get("source_review_required")
            ],
        }
    return {
        "required_scopes": sorted(set(scopes) & {"summary", "tasks", "help"}),
        "audience": audience,
        "recipient_id": actor.id,
        "start": week_start.isoformat(),
        "end": end.isoformat(),
        "timezone": tz.key,
        "counts": counts,
        "denominator": trend[-1]["denominator"],
        "daily": daily,
        "trend": trend,
        "activities": sorted(cohort, key=lambda r: (r["date"], r["id"])),
        "timeline": timeline[-200:],
        "timeline_total": len(timeline),
        "timeline_truncated": len(timeline) > 200,
        "help": [
            {"id": r.id, "status": r.status, "created_at": r.created_at}
            for r in helpers.values()
            if (t := timestamp(r.created_at)) and lower <= t < upper
        ],
        "clinical": clinical,
        "facts": facts,
        "data_quality": {
            "expected_activities": None,
            "dates_without_recorded_activities": sum(
                d["denominator"] == 0 for d in daily
            ),
            "invalid_activity_dates": invalid_dates,
        },
        "notes": [
            "Latest recorded states for activities scheduled or created in this interval; later responses can revise an earlier week.",
            "Completed means participant-reported, not independently observed. No confirmation does not establish a missed medicine or activity.",
            "Cancelled and superseded activities are excluded. One-time activities use creation date; routine activities use scheduled date.",
            "Historical schedule coverage cannot be reconstructed from current routine settings. No expected adherence denominator or cognitive-health score is calculated.",
            "Timeline entries record actions at their actual timestamps; titles use the current source record.",
        ],
    }


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    end_date: dt.date | None = None
    timezone: str = Field(default="Asia/Dubai", max_length=100)
    audience: Literal["family", "clinical"] = "clinical"
    recipient_id: str | None = Field(default=None, max_length=60)


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class Review(Revision):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=2000)


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    quote: str


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: list[Quote] = Field(min_length=1, max_length=8)


def packed(r, reviewer=False):
    p = r.payload
    result = {
        "id": r.id,
        "version": r.version,
        "status": r.status,
        "created_at": r.created_at,
        "snapshot": p["snapshot"],
        "generated_at": p["generated_at"],
        "summary": p.get("summary"),
        "approved_at": p.get("approved_at"),
        "producer": p.get("producer", "deterministic projection"),
    }
    if reviewer:
        result.update(
            review_note=p.get("review_note", ""), fingerprint=p["fingerprint"]
        )
    return result


def report_record(db, pid, rid):
    r = db.get(Record, rid)
    if not r or r.patient_id != pid or r.kind != "weekly_report":
        raise HTTPException(404, "Report not found")
    return r


def check_fresh(db, pid, u, r):
    p = r.payload
    sel = Selection(**p["selection"])
    actor = viewer(db, u, pid, sel.audience, sel.recipient_id)
    end, tz = selection(sel.end_date, sel.timezone)
    current = project(db, pid, actor, end, tz, sel.audience)
    if fingerprint(current) != p["fingerprint"]:
        raise HTTPException(
            409, "Source data changed; create a new snapshot before review"
        )


@router.get("/weekly")
def weekly(
    pid: str,
    end_date: dt.date | None = None,
    timezone: str = "Asia/Dubai",
    audience: Literal["family", "clinical"] = "family",
    recipient_id: str | None = None,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    actor = viewer(db, u, pid, audience, recipient_id)
    end, tz = selection(end_date, timezone)
    return project(db, pid, actor, end, tz, audience) | {"as_of": now()}


@router.get("/recipients")
def recipients(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    clinician(db, u, pid)
    return [
        {"id": user.id, "name": user.name}
        for user, grant in db.query(User, Grant)
        .join(Grant, Grant.user_id == User.id)
        .filter(
            Grant.patient_id == pid,
            Grant.active.is_(True),
            User.org == u.org,
            User.role == "family",
        )
        .all()
        if "summary" in grant.scopes
    ]


@router.post("/snapshots")
def create_snapshot(
    pid: str,
    body: Selection,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    clinician(db, u, pid)
    if body.audience == "family" and not body.recipient_id:
        raise HTTPException(422, "Family snapshots require an explicit recipient")
    actor = viewer(db, u, pid, body.audience, body.recipient_id)
    end, tz = selection(body.end_date, body.timezone)
    data = project(db, pid, actor, end, tz, body.audience)
    r = Record(
        patient_id=pid,
        kind="weekly_report",
        status="draft",
        payload={
            "selection": body.model_dump(mode="json") | {"end_date": end.isoformat()},
            "snapshot": data,
            "fingerprint": fingerprint(data),
            "generated_at": now(),
            "created_by": u.id,
        },
    )
    db.add(r)
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="report.created",
            detail={"audience": body.audience},
        )
    )
    db.commit()
    return packed(r, True)


@router.get("/snapshots")
def snapshots(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    authorize(db, u, pid, "summary")
    scopes = (
        db.query(Grant)
        .filter_by(user_id=u.id, patient_id=pid, active=True)
        .one()
        .scopes
    )
    reviewer = u.role == "clinician" and "review" in scopes
    query = (
        db.query(Record)
        .filter_by(patient_id=pid, kind="weekly_report")
        .order_by(Record.created_at.desc())
    )
    # Apply recipient filtering before limiting, so unrelated drafts cannot hide shared reports.
    if not reviewer:
        query = query.filter(
            Record.status == "approved",
            Record.payload["snapshot"]["audience"].as_string() == "family",
            Record.payload["snapshot"]["recipient_id"].as_string() == u.id,
        )
    return [
        packed(r, reviewer)
        for r in query.limit(12)
        if reviewer
        or set(r.payload["snapshot"].get("required_scopes", [])) <= set(scopes)
    ]


@router.post("/snapshots/{rid}/summarize")
async def summarize(
    pid: str,
    rid: str,
    body: Revision,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    patient = authorize(db, u, pid, "review")
    clinician(db, u, pid)
    r = report_record(db, pid, rid)
    if r.version != body.expected_version or r.status not in {
        "draft",
        "awaiting_review",
    }:
        raise HTTPException(409, "Refresh the editable report revision")
    if not patient.synthetic:
        raise HTTPException(403, "External report AI is limited to synthetic patients")
    check_fresh(db, pid, u, r)
    facts = r.payload["snapshot"]["facts"]
    prompt = (
        "Select up to eight useful facts for human review. Copy their text EXACTLY into quote and their id into source_id. No diagnosis, recommendations, inference or additional text. Facts: "
        + json.dumps(facts)
    )
    db.commit()  # Release patient lock during the network call.
    try:
        raw = await gateway.structured(
            "meta", settings.meta_draft_model, prompt, Summary.model_json_schema()
        )
        result = Summary.model_validate(raw)
        allowed = {f["id"]: f["text"] for f in facts}
        if any(allowed.get(q.source_id) != q.quote for q in result.observations) or len(
            {q.source_id for q in result.observations}
        ) != len(result.observations):
            raise ValueError("Unsupported summary")
    except ProviderUnavailable:
        raise HTTPException(
            503, "Report AI unavailable; factual snapshot remains available"
        ) from None
    except (ValueError, TypeError):
        raise HTTPException(
            502, "Summary failed evidence checks; no draft saved"
        ) from None
    db.expire_all()
    if not authorize(db, u, pid, "review").synthetic:
        raise HTTPException(403, "Synthetic patient restriction changed")
    clinician(db, u, pid)
    r = report_record(db, pid, rid)
    if r.version != body.expected_version or r.status not in {
        "draft",
        "awaiting_review",
    }:
        raise HTTPException(409, "Report changed during generation")
    check_fresh(db, pid, u, r)
    r.payload = r.payload | {
        "summary": result.model_dump(),
        "producer": settings.meta_draft_model + "; exact-fact validation",
    }
    r.status = "awaiting_review"
    r.version += 1
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="report.summarized",
            detail={"record": r.id},
        )
    )
    db.commit()
    return packed(r, True)


@router.post("/snapshots/{rid}/review")
def review(
    pid: str,
    rid: str,
    body: Review,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    clinician(db, u, pid)
    r = report_record(db, pid, rid)
    if r.version != body.expected_version or r.status not in {
        "draft",
        "awaiting_review",
    }:
        raise HTTPException(409, "Refresh the editable report revision")
    if body.decision == "approve":
        check_fresh(db, pid, u, r)
    r.status = "approved" if body.decision == "approve" else "rejected"
    r.version += 1
    r.payload = r.payload | {
        "review_note": body.note,
        "reviewed_by": u.id,
        "approved_at": now() if body.decision == "approve" else None,
    }
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="report.reviewed",
            detail={"record": r.id, "decision": body.decision},
        )
    )
    db.commit()
    return packed(r, True)
