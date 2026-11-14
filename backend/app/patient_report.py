"""The person's own period report. Facts they recorded, laid out by day, with what is missing listed rather than hidden.

No composite score, no normal/abnormal, no comparison with other people, no change bands (those stay clinician-only), no imaging or risk content,
and no causal wording. Performance numbers and WHO-5 answers and totals are not shown (the person's own records follow the same rule: a bare number invites worry). Observed, self-reported and routine
answers are kept in separate groups. A routine with no answer is "not answered", never "missed".
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import careplan as CP
from .models import ActivitySession, CarePlan, CarePlanItem, CarePlanReply, ConcernReport, ConcernEvent, Evidence, User
from .services import Refused, audit

HIDDEN_PREFIX = ("who5_",)          # the person is shown that it was completed, not the answers or a total
MAX_DAYS = 90


def _local_date(dt: datetime, tz: ZoneInfo) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).date().isoformat()


def build(db: Session, user: User, days: int = 11, end: str | None = None) -> dict:
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    if not 1 <= days <= MAX_DAYS:
        raise Refused(422, f"Choose between 1 and {MAX_DAYS} days.")
    tzn = CP.tz_name(db, user)
    tz = ZoneInfo(tzn)
    try:
        last = date.fromisoformat(end) if end else CP.local_today(db, user)
    except ValueError:
        raise Refused(422, "The date should look like 2026-11-14.")
    if last > CP.local_today(db, user):
        raise Refused(422, "The report cannot end in the future.")
    first = last - timedelta(days=days - 1)
    f, l = first.isoformat(), last.isoformat()

    sessions = [s for s in db.scalars(select(ActivitySession).where(ActivitySession.participant_id == user.id).order_by(ActivitySession.started_at))
                if f <= _local_date(s.started_at, tz) <= l]
    sid = {s.id for s in sessions}
    ev: dict[int, list[Evidence]] = {}
    for e in db.scalars(select(Evidence).where(Evidence.participant_id == user.id, Evidence.session_id.in_(sid or {-1}), Evidence.status == "current")):
        ev.setdefault(e.session_id, []).append(e)

    by_day: dict[str, list[dict]] = {}
    skipped = 0
    for s in sessions:
        vals = []
        for e in ev.get(s.id, []):
            if e.measure.startswith(HIDDEN_PREFIX) or e.kind == "observed":
                continue        # performance numbers are not shown to the person without context (as in their records); the clinician sees them
            if e.missing_reason:
                skipped += 1
            vals.append({"measure": e.measure, "kind": e.kind, "unit": e.unit, "value_num": e.value_num, "value_text": e.value_text,
                         "missing_reason": e.missing_reason, "quality": e.quality})
        by_day.setdefault(_local_date(s.started_at, tz), []).append({
            "id": s.id, "protocol_code": s.protocol_code, "status": s.status, "assisted": s.assisted, "interruptions": s.interruptions,
            "unwell_today": s.unwell_today, "values": vals, "shows_values": s.protocol_code not in ("who5", "reaction_time", "picture_sequence")})

    replies = list(db.scalars(select(CarePlanReply).where(CarePlanReply.participant_id == user.id, CarePlanReply.day >= f, CarePlanReply.day <= l).order_by(CarePlanReply.id)))
    per_item: dict[int, dict] = {}
    for r in replies:
        d = per_item.setdefault(r.item_id, {"done": set(), "not_today": set(), "difficulty": set()})
        if r.reply in d:
            d[r.reply].add(r.day)
    routines = []
    for iid, d in per_item.items():
        it = db.get(CarePlanItem, iid)
        routines.append({"item_id": iid, "title": it.title, "text_en": it.text_en, "text_ar": it.text_ar,
                         "marked_done_days": len(d["done"]), "not_today_days": len(d["not_today"]), "difficulty_days": len(d["difficulty"]),
                         "answered_days": len(d["done"] | d["not_today"] | d["difficulty"]), "label": "patient_reported"})
    accepted = db.scalar(select(CarePlan).where(CarePlan.participant_id == user.id, CarePlan.status == "accepted").order_by(CarePlan.version.desc()))

    all_days = [(first + timedelta(days=i)).isoformat() for i in range(days)]
    concerns = []
    for c in db.scalars(select(ConcernReport).where(ConcernReport.participant_id == user.id, ConcernReport.status != "draft").order_by(ConcernReport.id)):
        sent = db.scalar(select(ConcernEvent).where(ConcernEvent.report_id == c.id, ConcernEvent.kind == "sent"))
        if sent and f <= _local_date(sent.at, tz) <= l:
            concerns.append({"id": c.id, "topic": c.topic, "status": c.status, "sent_on": _local_date(sent.at, tz)})

    audit(db, user.id, "report.viewed", user.id, None)       # that it was opened, nothing about its content
    db.commit()
    return {
        "label": "patient_recorded", "timezone": tzn, "period": {"from": f, "to": l, "days": days},
        "days": [{"date": d, "sessions": by_day.get(d, [])} for d in all_days],
        "routines": routines, "routine_plan_accepted": bool(accepted),
        "missing": {"days_without_activity": [d for d in all_days if d not in by_day], "skipped_answers": skipped,
                    "note": "Days with nothing recorded are listed as nothing recorded. They are not treated as problems."},
        "concerns_sent": concerns,
        "not_included": ["scores", "comparison_with_others", "change_bands", "imaging", "risk"],
    }
