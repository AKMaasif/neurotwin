"""A traceable concern-to-follow-up path using existing records, never inferred health outcomes.

The assigned clinician explicitly links records and records outcomes. Acceptance and patient-reported
task replies are read from their original tables. Neither closes a concern or proves improvement.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from . import activity_analysis as AA, careplan as CP
from .models import CareJourney, CareJourneyEvent, CarePlan, CarePlanItem, CarePlanReply, ConcernReport, User, now
from .security import active_grant
from .services import Refused, audit

OUTCOMES = ("open", "follow_up_required", "resolved", "referred", "closed_no_action")
FINISHED = ("resolved", "referred", "closed_no_action")
NO_ACCESS = "Not found, or you do not have access."


def require_access(db, user, row, write=False):
    if row is None:
        raise Refused(404, NO_ACCESS)
    if user.role == "participant" and row.participant_id == user.id and not write:
        return
    if (user.role != "clinician" or row.clinician_id != user.id
            or active_grant(db, row.participant_id, user.id, "clinical_review") is None):
        raise Refused(404, NO_ACCESS)


def get(db, user, jid, write=False):
    row = db.get(CareJourney, jid)
    require_access(db, user, row, write)
    return row


def _snapshot(row):
    return {k: getattr(row, k) for k in ("plan_id", "analysis_run_id", "analysis_digest", "next_action", "follow_up_on", "outcome")}


def _event(db, row, user, kind, note=""):
    db.flush()  # optimistic revision advances before the append-only event is added
    db.add(CareJourneyEvent(journey_id=row.id, actor_id=user.id, revision=row.revision, kind=kind, note=note, snapshot=_snapshot(row)))
    audit(db, user.id, "care_journey." + kind, row.participant_id, f"journey:{row.id}")


def from_concern(db, user, concern_id):
    concern = db.get(ConcernReport, concern_id)
    if (user.role != "clinician" or concern is None or concern.recipient_id != user.id
            or active_grant(db, concern.participant_id, user.id, "clinical_review") is None):
        raise Refused(404, NO_ACCESS)
    if concern.status in ("draft", "withdrawn"):
        raise Refused(409, "Only a submitted concern can start a care journey.")
    existing = db.scalar(select(CareJourney).where(CareJourney.concern_id == concern_id))
    if existing:
        return existing
    row = CareJourney(concern_id=concern_id, participant_id=concern.participant_id, clinician_id=user.id)
    try:
        db.add(row)
        _event(db, row, user, "opened")
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(CareJourney).where(CareJourney.concern_id == concern_id))
        if row is None:
            raise
    return row


def update(db, user, row, values):
    require_access(db, user, row, True)
    if row.revision != values["expected_revision"]:
        raise Refused(409, "This journey changed in another window. Reload it before saving.")
    changes = {k: v for k, v in values.items() if k not in ("expected_revision", "note")}
    # Validate everything before mutating, so a refused request changes nothing.
    if "plan_id" in changes and changes["plan_id"] is not None:
        plan = db.get(CarePlan, changes["plan_id"])
        if plan is None or plan.participant_id != row.participant_id or plan.created_by != user.id:
            raise Refused(404, NO_ACCESS)
    if "analysis_run_id" in changes:
        rid = changes["analysis_run_id"]
        run = AA.load(rid) if rid else None
        if rid and (run is None or run["participant_id"] != row.participant_id):
            raise Refused(404, NO_ACCESS)
        if run and (run["state"] != "reviewed" or not (run.get("review") or {}).get("decisions")):
            raise Refused(409, "Review the analysis before linking it to a care journey.")
        if run and AA.source_status(db, run) != "current":
            raise Refused(409, "The analysis source is changed or unverified. Run and review a new analysis.")
        changes["analysis_digest"] = AA.review_digest(run) if run else None
    if changes.get("follow_up_on"):
        try:
            changes["follow_up_on"] = date.fromisoformat(changes["follow_up_on"]).isoformat()
        except (ValueError, TypeError):
            raise Refused(422, "Use a calendar date such as 2026-11-20.") from None
    outcome = changes.get("outcome", row.outcome)
    if outcome not in OUTCOMES:
        raise Refused(422, "Choose a recorded outcome.")
    note = CP._clean(values.get("note"), 500) or ""
    if outcome != row.outcome and (outcome in FINISHED or row.outcome in FINISHED) and not note:
        raise Refused(422, "Record the reason for closing or reopening this journey.")
    action = CP._clean(changes.get("next_action", row.next_action), 300) or ""
    due = changes.get("follow_up_on", row.follow_up_on)
    if outcome == "follow_up_required" and (not action or not due):
        raise Refused(422, "Follow-up needs an action and a date.")
    changes["next_action"] = action
    if all(getattr(row, k) == v for k, v in changes.items()) and not note:
        return row
    for k, v in changes.items():
        setattr(row, k, v)
    row.updated_at = now()
    try:
        _event(db, row, user, "updated", note)
        db.commit()
    except StaleDataError:
        db.rollback()
        raise Refused(409, "This journey changed in another window. Reload it before saving.") from None
    return row


def out(db, row, user):
    require_access(db, user, row)
    concern = db.get(ConcernReport, row.concern_id)
    plan = db.get(CarePlan, row.plan_id) if row.plan_id else None
    items = list(db.scalars(select(CarePlanItem).where(CarePlanItem.plan_id == row.plan_id))) if plan else []
    replies = list(db.scalars(select(CarePlanReply).where(CarePlanReply.item_id.in_([i.id for i in items])))) if items else []
    latest = {}
    for r in sorted(replies, key=lambda r: r.id):
        if r.reply in ("done", "not_today"):
            latest[(r.item_id, r.day)] = r.reply
    counts = {"done": sum(v == "done" for v in latest.values()), "not_today": sum(v == "not_today" for v in latest.values()),
              "difficulty": sum(r.reply == "difficulty" for r in replies), "label": "patient_reported"}
    events = list(db.scalars(select(CareJourneyEvent).where(CareJourneyEvent.journey_id == row.id).order_by(CareJourneyEvent.id)))
    analysis = None
    if row.analysis_run_id:
        run = AA.load(row.analysis_run_id)
        analysis = {"run_id": row.analysis_run_id, "state": run["state"] if run else "unavailable",
                    "source_status": AA.source_status(db, run) if run else "unavailable",
                    "review_unchanged": bool(run and AA.review_digest(run) == row.analysis_digest)}
    return {"id": row.id, "concern_id": row.concern_id, "participant_id": row.participant_id,
            "clinician": CP._name(db, row.clinician_id), "revision": row.revision, "concern_status": concern.status,
            "plan": {"id": plan.id, "version": plan.version, "status": plan.status} if plan else None,
            "analysis": analysis, "next_action": row.next_action, "follow_up_on": row.follow_up_on, "outcome": row.outcome,
            "responses": counts, "created_at": CP._iso(row.created_at), "updated_at": CP._iso(row.updated_at),
            "events": [{"id": e.id, "kind": e.kind, "by": CP._name(db, e.actor_id), "at": CP._iso(e.at), "revision": e.revision,
                        "note": e.note, "outcome": e.snapshot["outcome"]} for e in events]}


def list_for(db, user, pid):
    if user.id != pid and (user.role != "clinician" or active_grant(db, pid, user.id, "clinical_review") is None):
        raise Refused(404, NO_ACCESS)
    if user.role not in ("clinician", "participant"):
        raise Refused(404, NO_ACCESS)
    query = select(CareJourney).where(CareJourney.participant_id == pid).order_by(CareJourney.id.desc())
    if user.role == "clinician":
        query = query.where(CareJourney.clinician_id == user.id)
    return [out(db, row, user) for row in db.scalars(query)]
