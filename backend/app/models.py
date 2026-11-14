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
CONSENT_SCOPES = ("participation", "voice_recording", "family_imaging_summary")
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


DAY_PARTS = ("morning", "afternoon", "evening", "anytime")


PLAN_STATUS = ("draft", "sent", "accepted", "declined", "superseded")
PLAN_RESPONSES = ("accept", "question", "decline")
REPLY_KINDS = ("done", "not_today", "snooze", "difficulty")
DIFFICULTY_REASONS = ("too_tiring", "unclear", "inaccessible", "need_help")


class CarePlan(Base):
    """One version of a person's plan. A plan is a draft until the clinician sends it, and its routines become tasks only when the
    person accepts it. A change after acceptance is a new version (a new draft) that needs its own acceptance; older versions and
    everything recorded under them are kept. `legacy` marks routines that existed before acceptance was introduced."""
    __tablename__ = "care_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("care_plans.id"), nullable=True)
    legacy: Mapped[bool] = mapped_column(Boolean, default=False)


class PlanResponse(Base):
    """What the person said about a sent plan. Append-only. A question stays open until the clinician answers it (Stage 3)."""
    __tablename__ = "plan_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("care_plans.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    response: Mapped[str] = mapped_column(String(10))   # accept | question | decline
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)   # the clinician who read it
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Notification(Base):
    """A pointer to something that needs a person's attention. It names the kind of event and the record, never its content
    (no routine text, no question), so a notification list cannot leak health detail."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))        # plan_waiting | plan_accepted | plan_declined | plan_question
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # the care plan
    about_id: Mapped[str | None] = mapped_column(String(40), nullable=True)   # the participant it concerns (for a clinician)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssistantAction(Base):
    """A change the assistant proposed and is waiting for the person to confirm. Single use, short life, bound to the person.
    It holds the tool name and its checked arguments (ids, a day, minutes), never the person's words."""
    __tablename__ = "assistant_actions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tool: Mapped[str] = mapped_column(String(30))
    args: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)   # succeeded | failed


class AssistantMessage(Base):
    """The assistant conversation, kept so a follow-up ("it", "the other one", "yes") makes sense. This is conversational memory only:
    it is separate from clinical evidence and care messages, is shown to nobody but the person, is never given to a model, a clinician or
    family, and can be cleared or switched off by the person at any time. Old messages are pruned automatically."""
    __tablename__ = "assistant_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    who: Mapped[str] = mapped_column(String(4))                 # you | bot
    text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # what the bot answered, so the screen can be rebuilt
    ctx: Mapped[dict | None] = mapped_column(JSON, nullable=True)       # what "it", "yes" and "the other one" would refer to next
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class PatientPreference(Base):
    """Settings that belong to the person. The time zone decides what "today" means for their routines."""
    __tablename__ = "patient_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dubai")
    assistant_memory: Mapped[bool] = mapped_column(Boolean, default=True)   # keep the assistant conversation so follow-ups make sense
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CarePlanItem(Base):
    """One routine in a person's care plan, written by a clinician in their own words. No model writes or edits these.
    Stopping an item keeps it (and its history) in the record."""
    __tablename__ = "care_plan_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    text_en: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text_ar: Mapped[str | None] = mapped_column(String(300), nullable=True)
    day_part: Mapped[str] = mapped_column(String(10), default="anytime")
    weekdays: Mapped[list] = mapped_column(JSON, default=list)   # 0 = Monday ... 6 = Sunday; empty = every day
    status: Mapped[str] = mapped_column(String(10), default="active")   # active | stopped
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    stopped_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Structured fields (Stage 2). The clinician's own words stay in text_en / text_ar and are never rewritten.
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("care_plans.id"), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    time_hhmm: Mapped[str | None] = mapped_column(String(5), nullable=True)
    window_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    window_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    precautions: Mapped[str | None] = mapped_column(String(300), nullable=True)
    copied_from_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # a new plan version copies the routines it keeps
    extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # how the fields were proposed and approved (Stage 3)


class CarePlanReply(Base):
    """What the person said about a routine on one day. Self-reported; append-only, the latest reply for a day counts.
    No reply is not a reply: silence is never stored or counted as 'missed'."""
    __tablename__ = "care_plan_replies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("care_plan_items.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[str] = mapped_column(String(10))   # YYYY-MM-DD, the person's own day
    reply: Mapped[str] = mapped_column(String(10))  # done | not_today | snooze | difficulty
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)   # snooze: when the reminder returns
    reason: Mapped[str | None] = mapped_column(String(20), nullable=True)                    # difficulty: one of DIFFICULTY_REASONS
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idem_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)     # a retried request returns the first result
    recorded_by: Mapped[str | None] = mapped_column(String(40), nullable=True)               # a supporter's help is attributed (later stages)


class FamilyMessage(Base):
    """A short message from a family member to the person they are authorised to support. Care communication: it is
    kept apart from evidence, never read by clinicians through the app, and never sent to a model. A message exists
    as a draft until its writer has seen the preview and pressed Send."""
    __tablename__ = "family_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="draft")   # draft | sent | discarded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # the person's choice


class NativeScan(Base):
    """Original research MRI, deliberately separate from synthetic clinical participants."""
    __tablename__ = "native_scans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(40))
    declared_modality: Mapped[str] = mapped_column(String(20), default="T1w")
    files: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class NativeRun(Base):
    """Durable native processing attempt; retries create another run, preserving history."""
    __tablename__ = "native_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("native_scans.id"), index=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    stages: Mapped[list] = mapped_column(JSON)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    producer_version: Mapped[str] = mapped_column(String(40), default="neurotwin-native/0.1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
