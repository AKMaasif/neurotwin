"""Care plan and reminders.

A clinician writes routines for one person (in English, Arabic or both). The person sees today's routines in their
language, marked as written by their clinician, and can answer "Done" or "Not today". Rules kept here:

- Nothing is model-written. Text is the clinician's; there is no generation step to check.
- A reminder with no answer is nothing: it is not stored, counted or shown as missed. Clinicians see what the person
  chose to mark, labelled self-reported, never a rate or a gap.
- Stopping a routine keeps it and its answers; only active routines are shown to the person.
- Only a clinician with an active clinical_review grant can write or stop routines.
- The audit log records that a routine was added or stopped, never its text.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DAY_PARTS, CarePlanItem, CarePlanReply, User, now
from .services import Refused, audit

MAX_ACTIVE = 12
HISTORY_DAYS = 14


def _clean(text: str | None) -> str | None:
    text = " ".join((text or "").split())
    return text or None


def add_item(db: Session, clinician: User, participant_id: str, text_en: str | None, text_ar: str | None,
             day_part: str, weekdays: list[int]) -> CarePlanItem:
    text_en, text_ar = _clean(text_en), _clean(text_ar)
    if not text_en and not text_ar:
        raise Refused(422, "Write the routine in English, Arabic or both.")
    if day_part not in DAY_PARTS:
        raise Refused(422, "Time of day must be morning, afternoon, evening or anytime.")
    days = sorted(set(weekdays))
    if any(d not in range(7) for d in days):
        raise Refused(422, "Days must be numbers 0 (Monday) to 6 (Sunday).")
    count = len(db.scalars(select(CarePlanItem.id).where(CarePlanItem.participant_id == participant_id,
                                                         CarePlanItem.status == "active")).all())
    if count >= MAX_ACTIVE:
        raise Refused(409, f"A plan can hold {MAX_ACTIVE} active routines. Stop one before adding another.")
    item = CarePlanItem(participant_id=participant_id, created_by=clinician.id, text_en=text_en, text_ar=text_ar,
                        day_part=day_part, weekdays=[] if len(days) == 7 else days)
    db.add(item)
    db.flush()
    audit(db, clinician.id, "careplan.added", participant_id, f"item:{item.id}")
    db.commit()
    return item


def stop_item(db: Session, clinician: User, item: CarePlanItem, note: str | None) -> CarePlanItem:
    if item.status != "active":
        raise Refused(409, "This routine is already stopped.")
    item.status, item.stopped_by, item.stopped_at = "stopped", clinician.id, now()
    item.stop_note = _clean(note[:300] if note else None)
    audit(db, clinician.id, "careplan.stopped", item.participant_id, f"item:{item.id}")
    db.commit()
    return item


def person_day(day: str | None) -> date:
    """The person's own day as their device reports it. Accepted only within a day of the server's date."""
    today = datetime.now(timezone.utc).date()
    if not day:
        return today
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise Refused(422, "Day must look like 2026-11-10.") from None
    if abs((d - today).days) > 1:
        raise Refused(422, "That day is too far from today.")
    return d


def due_on(item: CarePlanItem, d: date) -> bool:
    return item.status == "active" and (not item.weekdays or d.weekday() in item.weekdays)


def todays(db: Session, participant: User, d: date) -> list[tuple[CarePlanItem, str | None]]:
    items = db.scalars(select(CarePlanItem).where(CarePlanItem.participant_id == participant.id,
                                                  CarePlanItem.status == "active").order_by(CarePlanItem.id)).all()
    order = {p: i for i, p in enumerate(DAY_PARTS)}
    out = [(i, latest_reply(db, i.id, d)) for i in items if due_on(i, d)]
    return sorted(out, key=lambda r: (order[r[0].day_part], r[0].id))


def latest_reply(db: Session, item_id: int, d: date) -> str | None:
    r = db.scalar(select(CarePlanReply).where(CarePlanReply.item_id == item_id, CarePlanReply.day == d.isoformat())
                  .order_by(CarePlanReply.id.desc()).limit(1))
    return r.reply if r else None


def reply(db: Session, participant: User, item: CarePlanItem, d: date, answer: str) -> CarePlanReply:
    if item.participant_id != participant.id or not due_on(item, d):
        raise Refused(404, "Not found, or you do not have access.")
    if answer not in ("done", "not_today"):
        raise Refused(422, "Answer must be done or not_today.")
    row = CarePlanReply(item_id=item.id, participant_id=participant.id, day=d.isoformat(), reply=answer)
    db.add(row)
    audit(db, participant.id, "careplan.replied", participant.id, f"item:{item.id}")
    db.commit()
    return row


def clinician_view(db: Session, participant_id: str) -> list[dict]:
    """Routines with what the person chose to mark in the last two weeks. Days with no mark are simply absent."""
    since = (datetime.now(timezone.utc).date() - timedelta(days=HISTORY_DAYS - 1)).isoformat()
    items = db.scalars(select(CarePlanItem).where(CarePlanItem.participant_id == participant_id)
                       .order_by(CarePlanItem.status, CarePlanItem.id.desc())).all()
    out = []
    for i in items:
        rows = db.scalars(select(CarePlanReply).where(CarePlanReply.item_id == i.id, CarePlanReply.day >= since)
                          .order_by(CarePlanReply.id)).all()
        latest: dict[str, str] = {r.day: r.reply for r in rows}
        out.append({"item": i, "marked": [{"day": d, "reply": r} for d, r in sorted(latest.items())]})
    return out
