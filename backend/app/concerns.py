"""Concern reports: something the person wants their clinician to know, and what happened to it.

States: draft -> sent -> delivered -> acknowledged -> reviewed -> closed (or withdrawn by the person before the clinician acknowledges it).
Every state change is an event with who did it and when, and the person is only ever told a state that has an event behind it:

- "delivered" means the report is in the clinician's in-app inbox (the server wrote it there). It does NOT mean anyone has read it.
- "acknowledged" exists only after the clinician pressed Acknowledge. No other signal (opening a list, a page load) counts as "seen".
- "reviewed" and "closed" are the clinician's own actions, each with an optional note.

Rules: the recipient is chosen by the server from the person's active clinical_review grants (never from typed or spoken words); the person
previews exactly what will be sent and the Send only goes through if nothing changed since that preview (rev); the words are the person's
own, labelled patient-reported, and are never scored, ranked or interpreted; this is not an emergency route and no one is promised to be
watching; the audit log records the event, never the words. A clinician whose access was removed no longer sees the report, but the record is kept.
"""
from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import careplan as CP
from .models import CONCERN_SINCE, CONCERN_TOPICS, ConcernEvent, ConcernReport, User, now
from .security import active_grant
from .services import Refused, audit

MAX_TEXT = 600
_NO = "Not found, or you do not have access."


def monitoring_hours() -> str | None:
    """Text supplied by the owner of the deployment saying when someone looks at the inbox. None means it has not been stated."""
    return (os.environ.get("NEUROTWIN_MONITORING_HOURS") or "").strip() or None


def recipients(db: Session, participant: User) -> list[dict]:
    """The clinicians this person has chosen to share with for clinical review, as the server sees it right now."""
    from .models import AccessGrant
    out = []
    for g in db.scalars(select(AccessGrant).where(AccessGrant.owner_id == participant.id, AccessGrant.purpose == "clinical_review", AccessGrant.revoked_at.is_(None))):
        u = db.get(User, g.grantee_id)
        if u is not None and u.role == "clinician":
            out.append({"id": u.id, "name": u.display_name})
    return out


def _event(db: Session, r: ConcernReport, kind: str, actor: str, note: str | None = None) -> None:
    db.add(ConcernEvent(report_id=r.id, kind=kind, actor_id=actor, note=CP._clean(note, 300)))


def _mine(db: Session, user: User, rid: int) -> ConcernReport:
    r = db.get(ConcernReport, rid)
    if r is None or r.participant_id != user.id or user.role != "participant":
        raise Refused(404, _NO)
    return r


def _check(topic: str, since: str, text: str) -> str:
    if topic not in CONCERN_TOPICS:
        raise Refused(422, "Choose what this is about.")
    if since not in CONCERN_SINCE:
        raise Refused(422, "Choose how long this has been going on, or not sure.")
    text = CP._clean(text) or ""
    if not text:
        raise Refused(422, "Write a few words about it first.")
    if len(text) > MAX_TEXT:
        raise Refused(422, f"Keep it under {MAX_TEXT} characters.")
    return text


def create(db: Session, user: User, topic: str, since: str, text: str) -> ConcernReport:
    if user.role != "participant":
        raise Refused(404, _NO)
    r = ConcernReport(participant_id=user.id, topic=topic, since=since, text=_check(topic, since, text))
    db.add(r)
    db.flush()
    _event(db, r, "created", user.id)
    audit(db, user.id, "concern.created", user.id, f"report:{r.id}")
    db.commit()
    return r


def edit(db: Session, user: User, rid: int, topic: str, since: str, text: str) -> ConcernReport:
    r = _mine(db, user, rid)
    if r.status != "draft":
        raise Refused(409, "Only a report that has not been sent can be changed.")
    r.topic, r.since, r.text = topic, since, _check(topic, since, text)
    r.rev += 1
    db.commit()
    return r


def send(db: Session, user: User, rid: int, rev: int, recipient_id: str | None) -> ConcernReport:
    """Send what the person previewed (same rev) to one clinician they have chosen to share with. The server picks the recipient from the
    grants; a recipient id is only accepted if it is on that list, and with exactly one clinician it is chosen automatically."""
    r = _mine(db, user, rid)
    if r.status != "draft":
        raise Refused(409, "This report was already sent.")
    if rev != r.rev:
        raise Refused(409, "This report changed after you previewed it. Please check it again before sending.")
    allowed = recipients(db, user)
    if not allowed:
        raise Refused(409, "You have not chosen a clinician to share with yet, so this cannot be sent. Your draft is saved.")
    if recipient_id is None and len(allowed) == 1:
        recipient_id = allowed[0]["id"]
    if recipient_id not in {a["id"] for a in allowed}:
        raise Refused(422, "Choose which clinician should receive it.")
    r.recipient_id = recipient_id
    r.status = "delivered"            # written into the clinician's in-app inbox in this same step; says nothing about it being read
    _event(db, r, "sent", user.id)
    _event(db, r, "delivered", user.id)
    CP.db_notify(db, recipient_id, "concern_sent", about=user.id, ref=r.id)
    audit(db, user.id, "concern.sent", user.id, f"report:{r.id}")
    db.commit()
    return r


def withdraw(db: Session, user: User, rid: int) -> ConcernReport:
    r = _mine(db, user, rid)
    if r.status == "draft":
        r.status = "withdrawn"
        _event(db, r, "withdrawn", user.id, "draft discarded")
    elif r.status in ("sent", "delivered"):
        r.status = "withdrawn"
        _event(db, r, "withdrawn", user.id)
        CP.db_notify(db, r.recipient_id, "concern_withdrawn", about=user.id, ref=r.id)
    else:
        raise Refused(409, "The clinician has already acknowledged this, so it cannot be withdrawn.")
    audit(db, user.id, "concern.withdrawn", user.id, f"report:{r.id}")
    db.commit()
    return r


# ---- views ---------------------------------------------------------------------------------------------------------

STATE_ORDER = ("delivered", "acknowledged", "reviewed", "closed")


def _events(db: Session, r: ConcernReport) -> list[dict]:
    return [{"kind": e.kind, "by": CP._name(db, e.actor_id), "at": CP._iso(e.at), "note": e.note}
            for e in db.scalars(select(ConcernEvent).where(ConcernEvent.report_id == r.id).order_by(ConcernEvent.id))]


def out(db: Session, r: ConcernReport, for_clinician: bool = False) -> dict:
    ev = _events(db, r)
    data = {"id": r.id, "status": r.status, "topic": r.topic, "since": r.since, "text": r.text, "rev": r.rev, "created_at": CP._iso(r.created_at),
            "recipient": CP._name(db, r.recipient_id), "events": ev, "label": "patient_reported"}
    if for_clinician:
        data["participant_id"] = r.participant_id
        data["participant"] = CP._name(db, r.participant_id)
    return data


def mine(db: Session, user: User) -> list[dict]:
    if user.role != "participant":
        raise Refused(404, _NO)
    rows = db.scalars(select(ConcernReport).where(ConcernReport.participant_id == user.id).order_by(ConcernReport.id.desc()).limit(50))
    return [out(db, r) for r in rows]


def inbox(db: Session, clinician: User) -> list[dict]:
    """Reports sent to this clinician by people who still share with them. Newest first; no ranking, no urgency label."""
    if clinician.role != "clinician":
        raise Refused(404, _NO)
    rows = db.scalars(select(ConcernReport).where(ConcernReport.recipient_id == clinician.id, ConcernReport.status != "draft").order_by(ConcernReport.id.desc()).limit(100))
    return [out(db, r, True) for r in rows if active_grant(db, r.participant_id, clinician.id, "clinical_review") is not None]


def _theirs(db: Session, clinician: User, rid: int) -> ConcernReport:
    r = db.get(ConcernReport, rid)
    if (clinician.role != "clinician" or r is None or r.recipient_id != clinician.id or r.status == "draft"
            or active_grant(db, r.participant_id, clinician.id, "clinical_review") is None):
        raise Refused(404, _NO)
    return r


def acknowledge(db: Session, clinician: User, rid: int) -> ConcernReport:
    r = _theirs(db, clinician, rid)
    if r.status == "withdrawn":
        raise Refused(409, "The person withdrew this report.")
    if r.status not in ("sent", "delivered"):
        return r                                                      # already acknowledged or beyond: nothing new to record
    r.status = "acknowledged"
    _event(db, r, "acknowledged", clinician.id)
    CP.db_notify(db, r.participant_id, "concern_acknowledged", about=r.participant_id, ref=r.id)
    audit(db, clinician.id, "concern.acknowledged", r.participant_id, f"report:{r.id}")
    db.commit()
    return r


def review(db: Session, clinician: User, rid: int, note: str | None) -> ConcernReport:
    r = _theirs(db, clinician, rid)
    if r.status == "withdrawn":
        raise Refused(409, "The person withdrew this report.")
    if r.status in ("sent", "delivered"):
        raise Refused(409, "Acknowledge the report before marking it reviewed.")
    if r.status == "closed":
        raise Refused(409, "This report is closed.")
    r.status = "reviewed"
    _event(db, r, "reviewed", clinician.id, note)
    CP.db_notify(db, r.participant_id, "concern_reviewed", about=r.participant_id, ref=r.id)
    audit(db, clinician.id, "concern.reviewed", r.participant_id, f"report:{r.id}")
    db.commit()
    return r


def close(db: Session, clinician: User, rid: int, note: str | None) -> ConcernReport:
    r = _theirs(db, clinician, rid)
    if r.status in ("withdrawn", "closed"):
        raise Refused(409, "This report is already finished.")
    if r.status in ("sent", "delivered"):
        raise Refused(409, "Acknowledge the report before closing it.")
    r.status = "closed"
    _event(db, r, "closed", clinician.id, note)
    CP.db_notify(db, r.participant_id, "concern_closed", about=r.participant_id, ref=r.id)
    audit(db, clinician.id, "concern.closed", r.participant_id, f"report:{r.id}")
    db.commit()
    return r
