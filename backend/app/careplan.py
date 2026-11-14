"""Care plan, acceptance and daily tasks.

The path a routine takes: the clinician writes it into a draft plan, adds its structured details, and sends the plan; the person reviews it
and accepts, asks a question or declines; only an ACCEPTED plan makes tasks. Rules kept here:

- Nothing is model-written here. The clinician's own words (`text_en`, `text_ar`) are the original instruction and are never rewritten.
- A change to an accepted plan is a new version (a new draft) that needs its own acceptance. The accepted version keeps running until then.
  Older versions, and every answer recorded under them, are kept. Stopping a routine takes effect at once (it can only reduce what is asked).
- Each routine on each day is one occurrence, shown from the person's own time zone. Answers are append-only; the latest done / not-today
  answer for a day counts, and a repeated identical answer or a retried request does not add a second record.
- No answer is not an answer: silence is never stored or shown as missed. A "done" is the person's own report, not a verified fact.
- Snoozing moves the reminder, never the instruction. A difficulty report is kept with its reason and is never counted as non-adherence.
- Only a clinician with an active clinical_review grant can write, send or stop routines; the audit log records what happened, never the text.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (DAY_PARTS, DIFFICULTY_REASONS, CarePlan, CarePlanItem, CarePlanReply, Notification, PatientPreference, PlanResponse, User, now)
from .services import Refused, audit

MAX_ACTIVE = 12
HISTORY_DAYS = 14
SNOOZE_MINUTES = (10, 30, 60, 120)
DEFAULT_TZ = os.environ.get("NEUROTWIN_DEFAULT_TIMEZONE") or "Asia/Dubai"
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DAY_DEFAULT = {"morning": "08:00", "afternoon": "13:00", "evening": "18:00", "anytime": "23:59"}
_NO_ACCESS = "Not found, or you do not have access."


def _clean(text: str | None, limit: int | None = None) -> str | None:
    text = " ".join((text or "").split())
    if limit and len(text) > limit:
        raise Refused(422, f"Keep this under {limit} characters.")
    return text or None


def notify(db: Session, user_id: str | None, kind: str, plan: CarePlan) -> None:
    """Queue a pointer for someone. It carries the kind and the plan id only, never any routine or question text."""
    if user_id:
        db.add(Notification(user_id=user_id, kind=kind, ref_id=plan.id, about_id=plan.participant_id))


def notifications(db: Session, user: User) -> list[dict]:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(50))
    return [{"id": n.id, "kind": n.kind, "plan_id": n.ref_id, "about_id": n.about_id, "about": _name(db, n.about_id) if user.role == "clinician" else None,
             "created_at": _iso(n.created_at), "read": n.read_at is not None} for n in rows]


def mark_read(db: Session, user: User, nid: int) -> None:
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise Refused(404, _NO_ACCESS)
    if n.read_at is None:
        n.read_at = now()
        db.commit()


# ---- the person's day ---------------------------------------------------------------------------------------

def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise Refused(422, "That time zone is not known. Use a name such as Asia/Dubai.") from None


def tz_name(db: Session, user: User) -> str:
    pref = db.get(PatientPreference, user.id)
    return pref.timezone if pref else DEFAULT_TZ


def local_now(db: Session, user: User) -> datetime:
    return datetime.now(zone(tz_name(db, user)))


def local_today(db: Session, user: User) -> date:
    """What "today" means for this person: the date in their own time zone, decided by the server, not by the device clock."""
    return local_now(db, user).date()


def set_timezone(db: Session, user: User, name: str) -> str:
    zone(name)
    pref = db.get(PatientPreference, user.id)
    if pref is None:
        db.add(PatientPreference(user_id=user.id, timezone=name))
    else:
        pref.timezone, pref.updated_at = name, now()
    audit(db, user.id, "preferences.timezone", user.id, None)
    db.commit()
    return name


def reply_day(db: Session, user: User, day: str | None) -> date:
    """The day an answer is for: today in the person's time zone, or the day before (a late answer or a retry after midnight)."""
    today = local_today(db, user)
    if not day:
        return today
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise Refused(422, "Day must look like 2026-11-10.") from None
    if d not in (today, today - timedelta(days=1)):
        raise Refused(422, "That day is not today or yesterday.")
    return d


# ---- plans --------------------------------------------------------------------------------------------------

def _plans(db: Session, pid: str, status: str) -> list[CarePlan]:
    return list(db.scalars(select(CarePlan).where(CarePlan.participant_id == pid, CarePlan.status == status).order_by(CarePlan.version.desc(), CarePlan.id.desc())))


def active_plan(db: Session, pid: str) -> CarePlan | None:
    return next(iter(_plans(db, pid, "accepted")), None)


def draft_plan(db: Session, pid: str) -> CarePlan | None:
    return next(iter(_plans(db, pid, "draft")), None)


def sent_plan(db: Session, pid: str) -> CarePlan | None:
    return next(iter(_plans(db, pid, "sent")), None)


def _items(db: Session, plan_id: int, only_active: bool = False) -> list[CarePlanItem]:
    q = select(CarePlanItem).where(CarePlanItem.plan_id == plan_id).order_by(CarePlanItem.id)
    if only_active:
        q = q.where(CarePlanItem.status == "active")
    return list(db.scalars(q))


def edit_plan(db: Session, clinician: User, pid: str) -> CarePlan:
    """The draft to write into: the existing draft, or a new version that starts as a copy of the accepted plan's routines."""
    draft = draft_plan(db, pid)
    if draft:
        return draft
    if sent_plan(db, pid):
        raise Refused(409, "A plan is waiting for the person to respond. Recall it first if you need to change it.")
    base = active_plan(db, pid)
    last = db.scalar(select(CarePlan.version).where(CarePlan.participant_id == pid).order_by(CarePlan.version.desc()).limit(1)) or 0
    draft = CarePlan(participant_id=pid, version=last + 1, status="draft", created_by=clinician.id, supersedes_id=base.id if base else None)
    db.add(draft)
    db.flush()
    if base:
        for i in _items(db, base.id, only_active=True):
            db.add(CarePlanItem(participant_id=pid, created_by=i.created_by, plan_id=draft.id, copied_from_id=i.id, text_en=i.text_en, text_ar=i.text_ar,
                                day_part=i.day_part, weekdays=list(i.weekdays or []), title=i.title, time_hhmm=i.time_hhmm, window_start=i.window_start,
                                window_end=i.window_end, start_date=i.start_date, end_date=i.end_date, quantity=i.quantity, unit=i.unit, precautions=i.precautions))
    audit(db, clinician.id, "careplan.draft_created", pid, f"plan:{draft.id}")
    return draft


def _check_time(value: str | None, what: str) -> str | None:
    if value in (None, ""):
        return None
    if not _HHMM.match(value):
        raise Refused(422, f"{what} must look like 08:30.")
    return value


def _check_date(value: str | None, what: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise Refused(422, f"{what} must look like 2026-11-10.") from None


def add_item(db: Session, clinician: User, participant_id: str, text_en: str | None, text_ar: str | None, day_part: str, weekdays: list[int], *,
             title: str | None = None, time_hhmm: str | None = None, window_start: str | None = None, window_end: str | None = None,
             start_date: str | None = None, end_date: str | None = None, quantity: float | None = None, unit: str | None = None,
             precautions: str | None = None, extraction: dict | None = None) -> CarePlanItem:
    text_en, text_ar = _clean(text_en), _clean(text_ar)
    if not text_en and not text_ar:
        raise Refused(422, "Write the routine in English, Arabic or both.")
    if day_part not in DAY_PARTS:
        raise Refused(422, "Time of day must be morning, afternoon, evening or anytime.")
    days = sorted(set(weekdays))
    if any(d not in range(7) for d in days):
        raise Refused(422, "Days must be numbers 0 (Monday) to 6 (Sunday).")
    time_hhmm, window_start, window_end = _check_time(time_hhmm, "Time"), _check_time(window_start, "Window start"), _check_time(window_end, "Window end")
    if time_hhmm and (window_start or window_end):
        raise Refused(422, "Give either a time or a time window, not both.")
    if bool(window_start) != bool(window_end) or (window_start and window_end and window_start >= window_end):
        raise Refused(422, "A time window needs a start before its end.")
    start_date, end_date = _check_date(start_date, "Start date"), _check_date(end_date, "End date")
    if start_date and end_date and end_date < start_date:
        raise Refused(422, "The end date cannot be before the start date.")
    unit = _clean(unit, 20)
    if (quantity is None) != (unit is None):
        raise Refused(422, "Give a quantity together with its unit, or neither. NeuroTwin never guesses a unit.")
    if quantity is not None and not 0 < quantity <= 10000:
        raise Refused(422, "The quantity must be more than 0.")
    plan = edit_plan(db, clinician, participant_id)
    if len([i for i in _items(db, plan.id, only_active=True)]) >= MAX_ACTIVE:
        raise Refused(409, f"A plan can hold {MAX_ACTIVE} routines. Stop one before adding another.")
    item = CarePlanItem(participant_id=participant_id, created_by=clinician.id, plan_id=plan.id, text_en=text_en, text_ar=text_ar, day_part=day_part,
                        weekdays=[] if len(days) == 7 else days, title=_clean(title, 120), time_hhmm=time_hhmm, window_start=window_start, window_end=window_end,
                        start_date=start_date, end_date=end_date, quantity=quantity, unit=unit, precautions=_clean(precautions, 300), extraction=extraction)
    db.add(item)
    db.flush()
    audit(db, clinician.id, "careplan.added", participant_id, f"item:{item.id}")
    db.commit()
    return item


def stop_item(db: Session, clinician: User, item: CarePlanItem, note: str | None) -> CarePlanItem:
    """Stopping applies at once. In a draft it removes the routine from the proposal; in the accepted plan it ends the task (history kept)."""
    if item.status != "active":
        raise Refused(409, "This routine is already stopped.")
    plan = db.get(CarePlan, item.plan_id) if item.plan_id else None
    if plan is not None and plan.status not in ("draft", "accepted"):
        raise Refused(409, "Only a draft or the accepted plan can be changed.")
    targets = [item]
    if plan is not None and plan.status == "accepted":   # a draft copy of it must not bring it back
        targets += list(db.scalars(select(CarePlanItem).where(CarePlanItem.copied_from_id == item.id, CarePlanItem.status == "active")))
    for t in targets:
        t.status, t.stopped_by, t.stopped_at = "stopped", clinician.id, now()
        t.stop_note = _clean(note[:300] if note else None)
    audit(db, clinician.id, "careplan.stopped", item.participant_id, f"item:{item.id}")
    db.commit()
    return item


def send_plan(db: Session, clinician: User, plan: CarePlan) -> CarePlan:
    if plan.status != "draft":
        raise Refused(409, "Only a draft can be sent.")
    if not _items(db, plan.id, only_active=True):
        raise Refused(409, "Add at least one routine before sending the plan.")
    plan.status, plan.sent_by, plan.sent_at = "sent", clinician.id, now()
    notify(db, plan.participant_id, "plan_waiting", plan)
    audit(db, clinician.id, "careplan.sent", plan.participant_id, f"plan:{plan.id}")
    db.commit()
    return plan


def recall_plan(db: Session, clinician: User, plan: CarePlan) -> CarePlan:
    if plan.status != "sent":
        raise Refused(409, "Only a plan that is waiting for the person can be recalled.")
    plan.status, plan.sent_at, plan.sent_by = "draft", None, None
    for n in db.scalars(select(Notification).where(Notification.ref_id == plan.id, Notification.kind == "plan_waiting", Notification.read_at.is_(None))):
        n.read_at = now()          # the plan is no longer waiting, so its notice is closed
    audit(db, clinician.id, "careplan.recalled", plan.participant_id, f"plan:{plan.id}")
    db.commit()
    return plan


def respond(db: Session, participant: User, plan: CarePlan, response: str, note: str | None = None) -> PlanResponse:
    """Accept, ask a question or decline. Only the person the plan is for can answer, and only while it is waiting for them."""
    if plan.participant_id != participant.id or participant.role != "participant":
        raise Refused(404, _NO_ACCESS)
    if response not in ("accept", "question", "decline"):
        raise Refused(422, "Response must be accept, question or decline.")
    if plan.status != "sent":
        raise Refused(409, "This plan is not waiting for a response." if plan.status != "accepted" or response != "accept" else "You have already accepted this plan.")
    note = _clean(note, 300)
    if response == "question" and not note:
        raise Refused(422, "Write your question first.")
    row = PlanResponse(plan_id=plan.id, participant_id=participant.id, response=response, note=note)
    db.add(row)
    if response == "accept":
        for old in _plans(db, plan.participant_id, "accepted"):
            old.status = "superseded"          # its tasks end here; its answers and history stay
        plan.status, plan.responded_at = "accepted", now()
    elif response == "decline":
        plan.status, plan.responded_at = "declined", now()
    notify(db, plan.sent_by, {"accept": "plan_accepted", "question": "plan_question", "decline": "plan_declined"}[response], plan)
    for n in db.scalars(select(Notification).where(Notification.user_id == participant.id, Notification.ref_id == plan.id, Notification.kind == "plan_waiting", Notification.read_at.is_(None))):
        if response != "question":
            n.read_at = now()
    audit(db, participant.id, f"careplan.{ {'accept': 'accepted', 'question': 'question', 'decline': 'declined'}[response] }", participant.id, f"plan:{plan.id}")
    db.commit()
    return row


# ---- today's tasks ------------------------------------------------------------------------------------------

def due_on(item: CarePlanItem, d: date) -> bool:
    iso = d.isoformat()
    return (item.status == "active" and (not item.weekdays or d.weekday() in item.weekdays)
            and (not item.start_date or item.start_date <= iso) and (not item.end_date or iso <= item.end_date))


def _time_key(item: CarePlanItem) -> str:
    return item.time_hhmm or item.window_start or _DAY_DEFAULT[item.day_part]


def _replies(db: Session, item_id: int, d: date) -> list[CarePlanReply]:
    return list(db.scalars(select(CarePlanReply).where(CarePlanReply.item_id == item_id, CarePlanReply.day == d.isoformat()).order_by(CarePlanReply.id)))


def state_of(rows: list[CarePlanReply], at: datetime) -> dict:
    """What the person has said about one routine on one day. Nothing said means nothing is shown."""
    done = next((r for r in reversed(rows) if r.reply in ("done", "not_today")), None)
    snooze = next((r for r in reversed(rows) if r.reply == "snooze"), None)
    diff = next((r for r in reversed(rows) if r.reply == "difficulty"), None)
    snoozed_until = None
    if snooze and snooze.until:
        until = snooze.until if snooze.until.tzinfo else snooze.until.replace(tzinfo=timezone.utc)
        if until > at and not (done and done.id > snooze.id):
            snoozed_until = until
    return {"reply": done.reply if done else None, "snoozed_until": snoozed_until, "difficulty": diff.reason if diff else None}


def todays(db: Session, participant: User, d: date) -> list[tuple[CarePlanItem, dict]]:
    plan = active_plan(db, participant.id)
    if plan is None:
        return []
    at = datetime.now(timezone.utc)
    out = [(i, state_of(_replies(db, i.id, d), at)) for i in _items(db, plan.id, only_active=True) if due_on(i, d)]
    return sorted(out, key=lambda r: (_time_key(r[0]), r[0].id))


def latest_reply(db: Session, item_id: int, d: date) -> str | None:
    return state_of(_replies(db, item_id, d), datetime.now(timezone.utc))["reply"]


def reply(db: Session, participant: User, item: CarePlanItem, d: date, answer: str, *, idem_key: str | None = None,
          snooze_minutes: int | None = None, reason: str | None = None, note: str | None = None) -> tuple[CarePlanReply, bool]:
    """Record one answer. Returns (row, duplicate): a retried request, or the same answer again, returns the earlier row and adds nothing."""
    plan = db.get(CarePlan, item.plan_id) if item.plan_id else None
    if item.participant_id != participant.id or participant.role != "participant" or plan is None or plan.status != "accepted" or not due_on(item, d):
        raise Refused(404, _NO_ACCESS)
    if answer not in ("done", "not_today", "snooze", "difficulty"):
        raise Refused(422, "Answer must be done, not_today, snooze or difficulty.")
    if idem_key:
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", idem_key):
            raise Refused(422, "The request key is not valid.")
        earlier = db.scalar(select(CarePlanReply).where(CarePlanReply.idem_key == idem_key))
        if earlier is not None:
            if earlier.participant_id != participant.id or earlier.item_id != item.id or earlier.reply != answer:
                raise Refused(409, "That request key was already used for something else.")
            return earlier, True
    rows = _replies(db, item.id, d)
    until = None
    if answer in ("done", "not_today"):
        last = next((r for r in reversed(rows) if r.reply in ("done", "not_today")), None)
        if last is not None and last.reply == answer:
            return last, True
    elif answer == "snooze":
        if snooze_minutes not in SNOOZE_MINUTES:
            raise Refused(422, f"Snooze for {', '.join(map(str, SNOOZE_MINUTES))} minutes.")
        z = zone(tz_name(db, participant))
        end_of_day = datetime.combine(d, time(23, 59), tzinfo=z).astimezone(timezone.utc)
        until = min(datetime.now(timezone.utc) + timedelta(minutes=snooze_minutes), end_of_day)
    else:
        if reason not in DIFFICULTY_REASONS:
            raise Refused(422, f"Reason must be one of {', '.join(DIFFICULTY_REASONS)}.")
    row = CarePlanReply(item_id=item.id, participant_id=participant.id, day=d.isoformat(), reply=answer, until=until,
                        reason=reason if answer == "difficulty" else None, note=_clean(note, 200) if answer == "difficulty" else None, idem_key=idem_key)
    db.add(row)
    audit(db, participant.id, "careplan.replied", participant.id, f"item:{item.id}")
    db.commit()
    return row, False


# ---- what each side sees --------------------------------------------------------------------------------------

def _name(db: Session, uid: str | None) -> str | None:
    u = db.get(User, uid) if uid else None
    return u.display_name if u else None


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def item_out(db: Session, i: CarePlanItem) -> dict:
    return {"id": i.id, "plan_id": i.plan_id, "text_en": i.text_en, "text_ar": i.text_ar, "day_part": i.day_part, "weekdays": i.weekdays or [], "status": i.status,
            "title": i.title, "time_hhmm": i.time_hhmm, "window_start": i.window_start, "window_end": i.window_end, "start_date": i.start_date, "end_date": i.end_date,
            "quantity": i.quantity, "unit": i.unit, "precautions": i.precautions, "created_at": _iso(i.created_at), "written_by": _name(db, i.created_by),
            "stopped_at": _iso(i.stopped_at), "stop_note": i.stop_note}


def plan_out(db: Session, p: CarePlan, items: list[dict] | None = None) -> dict:
    return {"id": p.id, "version": p.version, "status": p.status, "legacy": p.legacy, "created_at": _iso(p.created_at), "sent_at": _iso(p.sent_at),
            "responded_at": _iso(p.responded_at), "written_by": _name(db, p.created_by), "sent_by": _name(db, p.sent_by),
            "items": items if items is not None else [item_out(db, i) for i in _items(db, p.id)]}


def awaiting(db: Session, participant: User) -> list[dict]:
    """Plans the clinician has sent that the person has not yet answered, with who sent them and when."""
    return [{**plan_out(db, p, [item_out(db, i) for i in _items(db, p.id, only_active=True)]),
             "questions_asked": len([r for r in db.scalars(select(PlanResponse).where(PlanResponse.plan_id == p.id, PlanResponse.response == "question"))])}
            for p in _plans(db, participant.id, "sent")]


def review_response(db: Session, clinician: User, response_id: int, note: str | None) -> PlanResponse:
    """The clinician marks that they have read a response. Only then does anything say a clinician has seen it."""
    row = db.get(PlanResponse, response_id)
    if row is None:
        raise Refused(404, _NO_ACCESS)
    if row.reviewed_at is None:
        row.reviewed_by, row.reviewed_at, row.review_note = clinician.id, now(), _clean(note, 300)
        audit(db, clinician.id, "careplan.response_reviewed", row.participant_id, f"response:{row.id}")
        db.commit()
    return row


def history(db: Session, participant: User, days: int = 14) -> dict:
    """The person's own record: plans they answered and what they marked, newest first. Patient-reported, and silence is not listed."""
    days = max(1, min(days, 60))
    today = local_today(db, participant)
    since = (today - timedelta(days=days - 1)).isoformat()
    plans = [{"plan_id": p.id, "version": p.version, "status": p.status, "legacy": p.legacy, "sent_at": _iso(p.sent_at), "responded_at": _iso(p.responded_at),
              "by": _name(db, p.sent_by or p.created_by), "your_answers": [{"response": r.response, "at": _iso(r.at), "reviewed": r.reviewed_at is not None}
                                                                         for r in db.scalars(select(PlanResponse).where(PlanResponse.plan_id == p.id).order_by(PlanResponse.id))]}
             for p in db.scalars(select(CarePlan).where(CarePlan.participant_id == participant.id, CarePlan.status != "draft").order_by(CarePlan.version.desc()))]
    rows = list(db.scalars(select(CarePlanReply).where(CarePlanReply.participant_id == participant.id, CarePlanReply.day >= since).order_by(CarePlanReply.id)))
    by_day: dict[str, dict[int, dict]] = {}
    for r in rows:
        cell = by_day.setdefault(r.day, {}).setdefault(r.item_id, {"reply": None, "difficulty": None, "snoozed": False})
        if r.reply in ("done", "not_today"):
            cell["reply"] = r.reply
        elif r.reply == "difficulty":
            cell["difficulty"] = r.reason
        else:
            cell["snoozed"] = True
    out = []
    for day in sorted(by_day, reverse=True):
        entries = []
        for iid, cell in by_day[day].items():
            it = db.get(CarePlanItem, iid)
            entries.append({"item_id": iid, "text_en": it.text_en, "text_ar": it.text_ar, "title": it.title, **cell})
        out.append({"day": day, "entries": entries})
    return {"since": since, "until": today.isoformat(), "timezone": tz_name(db, participant), "label": "patient_reported", "plans": plans, "days": out}


def clinician_view(db: Session, participant_id: str) -> dict:
    """Every plan version with its routines, the person's answers to the plan, and what they chose to mark in the last two weeks."""
    since = (datetime.now(timezone.utc).date() - timedelta(days=HISTORY_DAYS)).isoformat()
    plans = list(db.scalars(select(CarePlan).where(CarePlan.participant_id == participant_id).order_by(CarePlan.version.desc(), CarePlan.id.desc())))
    out = []
    for p in plans:
        items = []
        for i in _items(db, p.id):
            rows = list(db.scalars(select(CarePlanReply).where(CarePlanReply.item_id == i.id, CarePlanReply.day >= since).order_by(CarePlanReply.id)))
            latest: dict[str, str] = {r.day: r.reply for r in rows if r.reply in ("done", "not_today")}
            hard = [{"day": r.day, "reason": r.reason, "note": r.note} for r in rows if r.reply == "difficulty"]
            items.append({**item_out(db, i), "marked": [{"day": d, "reply": r} for d, r in sorted(latest.items())], "difficulty": hard})
        resp = [{"id": r.id, "response": r.response, "note": r.note, "at": _iso(r.at), "reviewed_at": _iso(r.reviewed_at), "reviewed_by": _name(db, r.reviewed_by),
                 "review_note": r.review_note} for r in db.scalars(select(PlanResponse).where(PlanResponse.plan_id == p.id).order_by(PlanResponse.id))]
        out.append({**plan_out(db, p, items), "responses": resp})
    return {"plans": out, "draft_id": next((p["id"] for p in out if p["status"] == "draft"), None), "tz": None}
