"""Tables.

Three ideas run through every table:
- Who produced a record is always stored (producer type, id and version).
- Evidence is never overwritten. A correction is a new record that supersedes the old one; a withdrawal marks the
  record withdrawn and keeps it. Only `status` and `superseded_by_id` ever change on an evidence row, and only through
  `services.py`.
- Observed, self-reported and inferred records share a table but never a `kind`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


ROLES = ("participant", "family", "clinician")
EVIDENCE_KINDS = ("observed", "self_reported", "inferred")
PRODUCER_TYPES = ("person", "device", "rule", "model")
QUALITY_LEVELS = ("usable", "doubtful", "unusable")
EVIDENCE_STATUS = ("current", "amended", "withdrawn")
SESSION_STATUS = ("in_progress", "completed", "interrupted", "abandoned")
CONSENT_SCOPES = ("participation", "voice_recording")
GRANT_PURPOSES = ("participation_updates", "clinical_review")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(5), default="en")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str | None] = mapped_column(String(60), nullable=True, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LoginSession(Base):
    """A signed-in browser. Only a hash of its token is stored, so a copy of the database cannot be used to sign in."""
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConsentEvent(Base):
    """One row per decision. The current state of a scope is its newest row."""
    __tablename__ = "consent_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(40))
    decision: Mapped[str] = mapped_column(String(10))  # granted | withdrawn
    text_version: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(5))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AccessGrant(Base):
    __tablename__ = "access_grants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    grantee_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", foreign_keys=[owner_id])
    grantee = relationship("User", foreign_keys=[grantee_id])


class ActivitySession(Base):
    __tablename__ = "activity_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    protocol_code: Mapped[str] = mapped_column(String(40))
    protocol_version: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(5))
    device: Mapped[str] = mapped_column(String(80), default="unknown")
    assisted: Mapped[bool] = mapped_column(Boolean, default=False)
    assistance_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unwell_today: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = not asked / not answered
    interruptions: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("activity_sessions.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    measure: Mapped[str] = mapped_column(String(60))
    value_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    missing_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    protocol_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    protocol_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    producer_type: Mapped[str] = mapped_column(String(10))
    producer_id: Mapped[str] = mapped_column(String(80))
    producer_version: Mapped[str] = mapped_column(String(40))
    derived_from: Mapped[list] = mapped_column(JSON, default=list)
    quality: Mapped[str] = mapped_column(String(10))
    quality_reasons: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(10), default="current")
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    superseded_by_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewItem(Base):
    """A "To check" item: something a person should look at. Raised by rules, closed by a clinician."""
    __tablename__ = "review_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("activity_sessions.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(60))
    raised_by: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10), default="open")
    decision: Mapped[str | None] = mapped_column(String(10), nullable=True)  # keep | exclude
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Draft(Base):
    """A model-written summary and what became of it. The facts it was given are kept with it."""
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    language: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20))   # pending_review | approved | rejected | refused
    statements: Mapped[list] = mapped_column(JSON, default=list)
    problems: Mapped[list] = mapped_column(JSON, default=list)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    validator_version: Mapped[str] = mapped_column(String(40))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AuditEvent(Base):
    """Who did what to which record. Never holds health values or free text from participants."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(String(40))
    participant_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(80), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
