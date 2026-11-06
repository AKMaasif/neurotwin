import datetime as dt
import uuid
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.orm import (
    Session as OrmSession,
)

from .config import settings


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))
    org: Mapped[str] = mapped_column(String(60), default="demo")


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf: Mapped[str] = mapped_column(String(100))
    expires: Mapped[str] = mapped_column(String(50))


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    org: Mapped[str] = mapped_column(String(60), default="demo")
    name: Mapped[str] = mapped_column(String(150))
    age: Mapped[int] = mapped_column(Integer)
    region: Mapped[str] = mapped_column(String(80))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class Grant(Base):
    __tablename__ = "grants"
    __table_args__ = (UniqueConstraint("user_id", "patient_id"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    scopes: Mapped[list] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Record(Base):
    """Versioned, typed domain documents; patient binding is always checked by API."""

    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    actor: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class CareMessage(Base):
    __tablename__ = "care_messages"
    __table_args__ = (
        UniqueConstraint("sender_id", "command_id", name="uq_care_message_command"),
        Index(
            "ix_care_message_conversation",
            "patient_id",
            "sender_id",
            "recipient_id",
            "created_at",
            "id",
        ),
        Index("ix_care_message_timeline", "conversation_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    media: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    command_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(String(50), default=now)
    opened_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("care_conversations.id"), index=True, nullable=True
    )
    reply_to_id: Mapped[str | None] = mapped_column(
        ForeignKey("care_messages.id"), nullable=True
    )
    withdrawn_at: Mapped[str | None] = mapped_column(String(50), nullable=True)


class CareConversation(Base):
    __tablename__ = "care_conversations"
    __table_args__ = (UniqueConstraint("patient_id", "first_user", "second_user"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    first_user: Mapped[str] = mapped_column(ForeignKey("users.id"))
    second_user: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="active")
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class CareParticipant(Base):
    __tablename__ = "care_participants"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("care_conversations.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    grant_id: Mapped[str] = mapped_column(ForeignKey("grants.id"))
    joined_at: Mapped[str] = mapped_column(String(50), default=now)
    notifications: Mapped[bool] = mapped_column(Boolean, default=False)


class CareAttachment(Base):
    """Attachment metadata and its resumable upload session share one identity."""

    __tablename__ = "care_attachments"
    __table_args__ = (UniqueConstraint("uploader_id", "client_attachment_id"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("care_conversations.id"), index=True
    )
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    client_attachment_id: Mapped[str] = mapped_column(String(100))
    client_message_id: Mapped[str] = mapped_column(String(100))
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("care_messages.id"), index=True, nullable=True
    )
    filename: Mapped[str] = mapped_column(String(200))
    claimed_type: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(30))
    expected_size: Mapped[int] = mapped_column(Integer)
    offset: Mapped[int] = mapped_column(Integer, default=0)
    expected_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40), default="uploading")
    original_key: Mapped[str] = mapped_column(String(250))
    object_key: Mapped[str | None] = mapped_column(String(250), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expires_at: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class CareReceipt(Base):
    __tablename__ = "care_receipts"
    __table_args__ = (UniqueConstraint("message_id", "recipient_id"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    message_id: Mapped[str] = mapped_column(ForeignKey("care_messages.id"), index=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    delivered_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    playback_started_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    playback_completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)


class CareEvent(Base):
    """Durable transactional outbox; subscribers consume by conversation sequence."""

    __tablename__ = "care_events"
    __table_args__ = (UniqueConstraint("conversation_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("care_conversations.id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[str] = mapped_column(ForeignKey("care_messages.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class CareAudio(Base):
    __tablename__ = "care_audio"
    message_id: Mapped[str] = mapped_column(
        ForeignKey("care_messages.id"), primary_key=True
    )
    data: Mapped[bytes] = mapped_column(LargeBinary)


class SourceFile(Base):
    __tablename__ = "source_files"
    document_id: Mapped[str] = mapped_column(ForeignKey("records.id"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class DocumentUnit(Base):
    __tablename__ = "document_units"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("records.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[dict] = mapped_column(JSON)
    detail: Mapped[dict] = mapped_column(JSON)


class DocumentAsset(Base):
    __tablename__ = "document_assets"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("records.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    source: Mapped[dict] = mapped_column(JSON)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    mime: Mapped[str] = mapped_column(String(80), default="image/png")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("records.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    unit_id: Mapped[str] = mapped_column(ForeignKey("document_units.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[dict] = mapped_column(JSON)
    kind: Mapped[str] = mapped_column(String(40))
    terms: Mapped[dict] = mapped_column(JSON)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)


class DocumentJob(Base):
    __tablename__ = "document_jobs"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("records.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), index=True, default="queued")
    requested_by: Mapped[str] = mapped_column(String(60))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[str | None] = mapped_column(String(50), nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (UniqueConstraint("actor", "command_id"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String(60))
    command_id: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class Routine(Base):
    __tablename__ = "routines"
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[str] = mapped_column(ForeignKey("records.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="awaiting_consent")
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class RoutineOccurrence(Base):
    __tablename__ = "routine_occurrences"
    __table_args__ = (UniqueConstraint("routine_id", "local_date"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    routine_id: Mapped[str] = mapped_column(ForeignKey("routines.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("records.id"), unique=True)
    routine_version: Mapped[int] = mapped_column(Integer)
    local_date: Mapped[str] = mapped_column(String(10))
    scheduled_at: Mapped[str] = mapped_column(String(50))
    reminder_at: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    snoozes: Mapped[int] = mapped_column(Integer, default=0)
    help_id: Mapped[str | None] = mapped_column(ForeignKey("records.id"), nullable=True)
    resolution: Mapped[str] = mapped_column(String(80), default="wall_time")


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("occurrence_id", "recipient_id", "kind"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("routine_occurrences.id"), index=True
    )
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(30), default="available_in_app")
    version: Mapped[int] = mapped_column(Integer, default=1)
    seen_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acknowledged_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class DeviceNotice(Base):
    __tablename__ = "device_notices"
    __table_args__ = (UniqueConstraint("reminder_id", "device_id", "reminder_version"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=uid)
    reminder_id: Mapped[str] = mapped_column(ForeignKey("reminders.id"), index=True)
    reminder_version: Mapped[int] = mapped_column(Integer)
    device_id: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(30), default="claimed")
    created_at: Mapped[str] = mapped_column(String(50), default=now)


Path("data").mkdir(exist_ok=True)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")


Session = sessionmaker(engine, expire_on_commit=False)


@event.listens_for(OrmSession, "after_begin")
def messaging_actor(session, transaction, connection):
    if connection.dialect.name == "postgresql" and session.info.get("care_actor"):
        from sqlalchemy import text

        connection.execute(
            text("SELECT set_config('neurotwin.actor_id', :actor, true)"),
            {"actor": session.info["care_actor"]},
        )


def get_db():
    with Session() as db:
        yield db
