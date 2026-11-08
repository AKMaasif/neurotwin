"""Patient companion proposals and explicitly consented, bounded conversation memory."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from .ai import ProviderUnavailable, gateway, local_intent
from .arabic import command as language_command
from .arabic import localize as localize_result
from .db import Audit, Grant, Record, User, get_db, now
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/companion", tags=["Companion"])
DEFAULT_MEMORY = {
    "enabled": False,
    "share_with_ai": False,
    "preferred_name": "",
    "speech_rate": "normal",
    "history": [],
}


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=3000)
    locale: Literal["en", "ar"] = "en"
    task_id: str | None = Field(default=None, max_length=60)
    task_version: int | None = Field(default=None, ge=1)
    step_index: int = Field(default=0, ge=0, le=20)


class MemorySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    enabled: bool
    share_with_ai: bool = False
    preferred_name: str = Field(default="", max_length=60)
    speech_rate: Literal["normal", "slow"] = "normal"

    @model_validator(mode="after")
    def consent(self):
        if self.share_with_ai and not self.enabled:
            raise ValueError("Enable memory before sharing it with AI")
        return self


def memory_row(db, pid):
    return db.query(Record).filter_by(patient_id=pid, kind="companion_memory").first()


def memory_data(row):
    data = DEFAULT_MEMORY | (row.payload if row else {})
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    history = (
        [h for h in data["history"] if h["at"] >= cutoff][-6:]
        if data["enabled"]
        else []
    )
    if row and history != data["history"]:
        row.payload = data | {"history": history}
        row.version += 1
    return data | {"history": history}


def participant(db, u, pid):
    authorize(db, u, pid, "preferences")
    if u.role != "participant":
        raise HTTPException(403, "Conversation memory belongs to the participant")


@router.get("/memory")
def get_memory(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    participant(db, u, pid)
    row = memory_row(db, pid)
    data = memory_data(row)
    db.commit()
    return data | {"version": row.version if row else 0, "retention_days": 7}


@router.post("/memory")
def save_memory(
    pid: str,
    body: MemorySettings,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    participant(db, u, pid)
    row = memory_row(db, pid)
    if body.expected_version != (row.version if row else 0):
        raise HTTPException(409, "Memory settings changed; refresh before saving")
    old = memory_data(row)
    data = body.model_dump(exclude={"expected_version"}) | {
        "history": old["history"] if body.enabled else []
    }
    if not body.enabled:
        data = DEFAULT_MEMORY.copy()
    if row:
        row.payload = data
        row.version += 1
    else:
        row = Record(
            patient_id=pid, kind="companion_memory", status="active", payload=data
        )
        db.add(row)
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="companion.memory_consent",
            detail={"enabled": data["enabled"], "share_with_ai": data["share_with_ai"]},
        )
    )
    db.commit()
    return data | {"version": row.version, "retention_days": 7}


@router.post("/memory/forget")
def forget_memory(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    participant(db, u, pid)
    row = memory_row(db, pid)
    if row:
        row.payload = DEFAULT_MEMORY.copy()
        row.version += 1
    db.add(
        Audit(
            patient_id=pid, actor=u.id, action="companion.memory_forgotten", detail={}
        )
    )
    db.commit()
    return DEFAULT_MEMORY | {"version": row.version if row else 0, "retention_days": 7}


@router.post("/memory/export")
def export_memory(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    """Participant-only, explicit export of retained companion memory, not medical records."""
    participant(db, u, pid)
    row = memory_row(db, pid)
    data = memory_data(row)
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="companion.memory_exported",
            detail={"version": row.version if row else 0},
        )
    )
    result = {
        "schema_version": "neurotwin.companion-memory.v1",
        "patient_id": pid,
        "exported_at": now(),
        "retention_days": 7,
        "version": row.version if row else 0,
        "memory": data,
        "scope": "Retained companion preferences and text turns only. Excludes messages, medical records and raw audio.",
    }
    db.commit()
    return JSONResponse(
        result,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="neurotwin-companion-memory.json"',
        },
    )


@router.get("/contacts")
def contacts(pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    authorize(db, u, pid, "help")
    rows = (
        db.query(User, Grant)
        .join(Grant, Grant.user_id == User.id)
        .filter(
            Grant.patient_id == pid,
            Grant.active.is_(True),
            User.org == u.org,
            User.id != u.id,
        )
        .all()
    )
    result = [
        {"id": user.id, "name": user.name, "role": user.role}
        for user, grant in rows
        if "help" in grant.scopes
    ]
    result.sort(key=lambda c: (c["role"] == "clinician", c["name"]))
    db.commit()
    return result


def current_task(db, pid, body):
    tasks = (
        db.query(Record)
        .filter_by(patient_id=pid, kind="task")
        .order_by(Record.created_at, Record.id)
        .all()
    )
    tasks = [t for t in tasks if not t.payload.get("is_routine_template")]
    selected = (
        next((t for t in tasks if t.id == body.task_id), None)
        if body.task_id
        else next((t for t in tasks if t.status in ["pending", "deferred"]), None)
    )
    if not selected:
        return None
    from .routines import validate_scheduled_task

    validate_scheduled_task(db, selected)
    plan = db.get(Record, selected.payload["plan_id"])
    if (
        not plan
        or plan.status != "approved"
        or plan.payload.get("source_review_required")
        or plan.version != selected.payload["plan_version"]
        or selected.status == "superseded"
    ):
        raise HTTPException(
            409,
            "This activity needs care-team review. Refresh your plan before continuing.",
        )
    if body.task_version is not None and selected.version != body.task_version:
        raise HTTPException(409, "Activity changed; refresh before continuing")
    return selected


def local_result(db, u, pid, body):
    text = language_command(body.text).casefold().strip().rstrip(".!?")
    if any(
        x in text
        for x in ["sudden confusion", "chest pain", "cannot breathe", "can't breathe"]
    ):
        return {
            "intent": "clinical_review",
            "explanation": "Do not wait for this app. Use your locally approved urgent-help route or contact a person who can help now. No emergency service has been contacted.",
            "source": "local_safety_template",
            "action_status": "not_executed",
        }
    if text in ["stop", "cancel", "cancel that"]:
        return {
            "intent": "stop",
            "explanation": "Stopped. No new action was confirmed.",
            "action_status": "not_executed",
        }
    if text in [
        "what should i do",
        "what is next",
        "next activity",
        "guide my activity",
        "next step",
        "repeat this step",
        "i finished",
        "mark this done",
        "do this later",
    ]:
        authorize(
            db,
            u,
            pid,
            "respond"
            if text in ["i finished", "mark this done", "do this later"]
            else "tasks",
        )
        task = current_task(db, pid, body)
        if not task:
            return {
                "intent": "clarify",
                "explanation": "No unconfirmed activity is available. Your care team can review your plan.",
            }
        ref = {"id": task.id, "version": task.version, "title": task.payload["title"]}
        if text in ["i finished", "mark this done", "do this later"]:
            response = "deferred" if text == "do this later" else "completed"
            return {
                "intent": "task_response",
                "explanation": f'Ready to record "{task.payload["title"]}" as '
                + ("later." if response == "deferred" else "done.")
                + " Please confirm.",
                "requires_confirmation": True,
                "task": ref,
                "response": response,
            }
        steps = task.payload["steps"]
        index = body.step_index + (1 if text == "next step" else 0)
        index = min(index, max(0, len(steps) - 1))
        return {
            "intent": "coach_task",
            "explanation": steps[index]
            if steps
            else "Ask your care team to provide activity instructions.",
            "task": ref,
            "steps": steps,
            "step_index": index,
            "source": "approved_plan",
        }
    if text in ["did my family accept", "help request status", "who is helping me"]:
        authorize(db, u, pid, "help")
        helps = (
            db.query(Record)
            .filter_by(patient_id=pid, kind="help")
            .order_by(Record.created_at.desc())
            .all()
        )
        item = next(
            (
                h
                for h in helps
                if u.id in [h.payload["sender_id"], h.payload["recipient_id"]]
            ),
            None,
        )
        explanation = "No help request is saved."
        if item:
            recipient = db.get(User, item.payload["recipient_id"])
            grant = (
                db.query(Grant)
                .filter_by(
                    patient_id=pid, user_id=item.payload["recipient_id"], active=True
                )
                .first()
            )
            if grant and "help" in grant.scopes and recipient:
                states = {
                    "requested": " has not accepted your latest request yet.",
                    "accepted": " accepted responsibility for your latest request.",
                    "resolved": "'s latest request was closed after an activity update.",
                    "closed_unconfirmed": "'s follow-up window ended without activity confirmation.",
                    "cancelled": "'s latest request was cancelled.",
                }
                explanation = recipient.name + states.get(
                    item.status, " has a saved request for you to review."
                )
            else:
                explanation = "The contact for your latest request no longer has access. Choose a current contact."
        return {
            "intent": "help_status",
            "explanation": explanation,
            "source": "saved_help_record",
        }
    return None


@router.post("")
async def companion(
    pid: str,
    body: Turn,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    p = authorize(db, u, pid, "summary")
    row = memory_row(db, pid) if u.role == "participant" else None
    memory = memory_data(row)
    memory_version = row.version if row else 0
    result = local_result(db, u, pid, body)
    if result is None:
        proposal = local_intent(language_command(body.text))
        source = "local_parser"
        if proposal is None:
            if not p.synthetic:
                raise HTTPException(
                    403, "External model processing is not enabled for real records"
                )
            context = (
                {
                    "preferences": {
                        "preferred_name": memory["preferred_name"],
                        "speech_rate": memory["speech_rate"],
                    },
                    "previous_turns": memory["history"][-3:],
                }
                if memory["enabled"] and memory["share_with_ai"]
                else None
            )
            db.commit()  # release the patient lock while awaiting the provider
            try:
                proposal = await gateway.intent(body.text, context=context)
                source = "gemini_structured"
            except (ProviderUnavailable, ValueError):
                proposal = None
            db.expire_all()
            authorize(db, u, pid, "summary")
            row = memory_row(db, pid) if u.role == "participant" else None
            if (row.version if row else 0) != memory_version:
                raise HTTPException(409, "Companion memory changed; please try again")
            if proposal is None:
                result = {
                    "intent": "clarify",
                    "explanation": "I can open a page, read your approved plan, guide an activity, change text size, or prepare a help request. Which would you like?",
                    "source": "deterministic_fallback",
                    "action_status": "not_executed",
                }
        if proposal is not None:
            result = proposal.model_dump() | {
                "source": source,
                "action_status": "proposal_only",
            }
            if proposal.intent == "set_text_size":
                authorize(db, u, pid, "preferences")
                result.update(
                    text_size="large",
                    requires_confirmation=True,
                    explanation="Make the text larger? Please confirm.",
                )
            elif proposal.intent == "read_plan":
                plan = (
                    db.query(Record)
                    .filter_by(patient_id=pid, kind="plan", status="approved")
                    .first()
                )
                result["explanation"] = (
                    (
                        "A source for your plan was corrected. Please ask your care team to review the affected instructions."
                        if plan.payload.get("source_review_required")
                        else plan.payload["instructions"]
                    )
                    if plan
                    else "No approved plan is available."
                )
            elif proposal.intent == "prepare_help":
                authorize(db, u, pid, "help")
                result.update(
                    requires_confirmation=True,
                    explanation="Choose a current contact and confirm your request. It has not been sent.",
                )
            elif proposal.intent == "navigate":
                if proposal.screen == "messages":
                    authorize(db, u, pid, "messages")
                result["explanation"] = "Open " + proposal.screen + "."
            else:
                result["explanation"] = (
                    "Please choose a supported app action, or contact your care team about a clinical concern."
                )
    result.setdefault("source", "local_parser")
    result.setdefault("action_status", "proposal_only")
    result = localize_result(result, body.locale)
    result["speech_rate"] = memory["speech_rate"] if memory["enabled"] else "normal"
    if row and memory["enabled"]:
        row.payload = memory | {
            "history": (
                memory["history"]
                + [
                    {
                        "user": body.text[:1000],
                        "assistant": result["explanation"][:1500],
                        "at": now(),
                    }
                ]
            )[-6:]
        }
        row.version += 1
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="companion.proposal",
            detail={"intent": result["intent"], "source": result["source"]},
        )
    )
    db.commit()
    result["memory_version"] = row.version if row else 0
    return result
