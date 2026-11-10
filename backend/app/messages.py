"""Family messages: write, preview, then send.

- Only a family member with an active participation_updates grant from the person can write to them, and the grant
  is checked again at the moment of sending.
- A message is first a draft. The preview shows exactly the text and the recipient; nothing reaches the person until
  the writer presses Send. A new draft replaces an older unsent one.
- Plain text only, up to 300 characters, no web addresses (a message from a "relative" must not carry a link).
- The person can mark messages read and remove them from their own view; the record is kept.
- No clinician route reads these, no model sees them, and the audit log records only that a message was written,
  sent or removed.
- A sender may send five messages a day to one person, so the app cannot be used to flood someone.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import FamilyMessage, User, now
from .security import active_grant
from .services import Refused, audit

MAX_CHARS = 300
DAILY_LIMIT = 5
_LINK = re.compile(r"(https?:|www\.|\b[\w-]+\.(?:com|net|org|ae|io|me|co|info|app|link|ly)\b)", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f‪-‮⁦-⁩]")


def _may_write(db: Session, sender: User, participant_id: str) -> None:
    if sender.role != "family" or active_grant(db, participant_id, sender.id, "participation_updates") is None:
        raise Refused(404, "Not found, or you do not have access.")


def clean(text: str) -> str:
    text = "\n".join(" ".join(line.split()) for line in _CONTROL.sub("", text or "").splitlines()).strip()
    if not text:
        raise Refused(422, "Write a message first.")
    if len(text) > MAX_CHARS:
        raise Refused(422, f"Keep the message to {MAX_CHARS} characters or fewer.")
    if _LINK.search(text):
        raise Refused(422, "Messages cannot contain web addresses.")
    return text


def make_draft(db: Session, sender: User, participant_id: str, text: str) -> FamilyMessage:
    _may_write(db, sender, participant_id)
    text = clean(text)
    for old in db.scalars(select(FamilyMessage).where(FamilyMessage.sender_id == sender.id,
                                                      FamilyMessage.participant_id == participant_id,
                                                      FamilyMessage.status == "draft")):
        old.status = "discarded"
    m = FamilyMessage(sender_id=sender.id, participant_id=participant_id, text=text)
    db.add(m)
    db.flush()
    audit(db, sender.id, "message.drafted", participant_id, f"message:{m.id}")
    db.commit()
    return m


def _own(db: Session, sender: User, message_id: int) -> FamilyMessage:
    m = db.get(FamilyMessage, message_id)
    if m is None or m.sender_id != sender.id:
        raise Refused(404, "Not found, or you do not have access.")
    return m


def send(db: Session, sender: User, message_id: int) -> FamilyMessage:
    m = _own(db, sender, message_id)
    if m.status != "draft":
        raise Refused(409, "This message is not waiting to be sent.")
    _may_write(db, sender, m.participant_id)
    since = now() - timedelta(days=1)
    sent = db.scalar(select(func.count()).select_from(FamilyMessage).where(
        FamilyMessage.sender_id == sender.id, FamilyMessage.participant_id == m.participant_id,
        FamilyMessage.status == "sent", FamilyMessage.sent_at > since))
    if sent >= DAILY_LIMIT:
        raise Refused(429, f"You can send {DAILY_LIMIT} messages a day to one person. Try again tomorrow.")
    m.status, m.sent_at = "sent", now()
    audit(db, sender.id, "message.sent", m.participant_id, f"message:{m.id}")
    db.commit()
    return m


def discard(db: Session, sender: User, message_id: int) -> FamilyMessage:
    m = _own(db, sender, message_id)
    if m.status != "draft":
        raise Refused(409, "Only an unsent draft can be discarded.")
    m.status = "discarded"
    audit(db, sender.id, "message.discarded", m.participant_id, f"message:{m.id}")
    db.commit()
    return m


def written_by(db: Session, sender: User, participant_id: str) -> list[FamilyMessage]:
    _may_write(db, sender, participant_id)
    return list(db.scalars(select(FamilyMessage).where(
        FamilyMessage.sender_id == sender.id, FamilyMessage.participant_id == participant_id,
        FamilyMessage.status != "discarded").order_by(FamilyMessage.id.desc()).limit(20)))


def inbox(db: Session, person: User) -> list[FamilyMessage]:
    return list(db.scalars(select(FamilyMessage).where(
        FamilyMessage.participant_id == person.id, FamilyMessage.status == "sent",
        FamilyMessage.hidden_at.is_(None)).order_by(FamilyMessage.sent_at.desc()).limit(50)))


def _mine(db: Session, person: User, message_id: int) -> FamilyMessage:
    m = db.get(FamilyMessage, message_id)
    if m is None or m.participant_id != person.id or m.status != "sent":
        raise Refused(404, "Not found, or you do not have access.")
    return m


def mark_read(db: Session, person: User, message_id: int) -> None:
    m = _mine(db, person, message_id)
    if m.read_at is None:
        m.read_at = now()
        db.commit()


def hide(db: Session, person: User, message_id: int) -> None:
    m = _mine(db, person, message_id)
    m.hidden_at = now()
    audit(db, person.id, "message.removed_from_view", person.id, f"message:{m.id}")
    db.commit()


def sender_name(db: Session, m: FamilyMessage) -> str:
    u = db.get(User, m.sender_id)
    return u.display_name if u else "—"
