"""HTTP API. Thin: it checks who is asking, hands the work to services.py and shapes the reply."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import change as C
from . import config
from . import careplan as CP
from . import extraction as EX
from . import assistant as AS
from . import concerns as CN
from . import emergency as EM
from . import drafts as D
from . import llm
from . import messages as M
from . import voice as V
from . import protocols as P
from . import quality as Q
from . import services as S
from .db import Database
from .logs import SafeRequestLog
from .models import AccessGrant, ActivitySession, AuditEvent, CarePlan, CarePlanItem, Draft, FamilyMessage, Evidence, PlanResponse, ReviewItem, User
from .auth import router as auth_router
from .auth import user_out
from .imaging import router as imaging_router
from .oasis2_api import router as oasis2_router
from .agent_analysis_api import router as agent_router
from .native_imaging_api import ImagingRequestGuard, router as native_imaging_router
from .security import current_user, get_db, require_evidence_access

Lang = Literal["en", "ar"]


# ---- Request bodies ------------------------------------------------------------------------------------------

class CarePlanIn(BaseModel):
    text_en: str | None = Field(default=None, max_length=300)
    text_ar: str | None = Field(default=None, max_length=300)
    day_part: str = "anytime"
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    title: str | None = Field(default=None, max_length=120)
    time_hhmm: str | None = Field(default=None, max_length=5)
    window_start: str | None = Field(default=None, max_length=5)
    window_end: str | None = Field(default=None, max_length=5)
    start_date: str | None = Field(default=None, max_length=10)
    end_date: str | None = Field(default=None, max_length=10)
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=20)
    precautions: str | None = Field(default=None, max_length=300)


class PlanResponseIn(BaseModel):
    response: Literal["accept", "question", "decline"]
    note: str | None = Field(default=None, max_length=300)


class AssistantIn(BaseModel):
    text: str = Field(max_length=300)


class AssistantConfirmIn(BaseModel):
    confirmation_id: str = Field(min_length=8, max_length=40)


class ConcernIn(BaseModel):
    topic: str = Field(max_length=24)
    since: str = Field(max_length=14)
    text: str = Field(max_length=700)


class ConcernSendIn(BaseModel):
    rev: int
    recipient_id: str | None = Field(default=None, max_length=40)


class TrustedIn(BaseModel):
    name: str = Field(max_length=80)
    phone: str = Field(max_length=24)


class MemoryIn(BaseModel):
    enabled: bool


class SuggestIn(BaseModel):
    text_en: str | None = Field(default=None, max_length=300)
    text_ar: str | None = Field(default=None, max_length=300)


class TimezoneIn(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)


class MessageIn(BaseModel):
    participant_id: str = Field(min_length=1, max_length=40)
    text: str = Field(max_length=1000)


class CarePlanStopIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class CarePlanReplyIn(BaseModel):
    reply: Literal["done", "not_today", "snooze", "difficulty"]
    day: str | None = None
    idem_key: str | None = Field(default=None, max_length=64)
    snooze_minutes: int | None = None
    reason: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=200)


class ConsentIn(BaseModel):
    scope: str
    granted: bool
    language: Lang = "en"


class GrantIn(BaseModel):
    grantee_id: str
    purpose: str


class SessionStartIn(BaseModel):
    protocol_code: str
    protocol_version: str
    language: Lang = "en"
    device: str = Field(default="web", max_length=80)
    assisted: bool = False
    assistance_note: str | None = Field(default=None, max_length=200)
    unwell_today: bool | None = None


class ObservationBody(BaseModel):
    measure: str
    kind: Literal["observed", "self_reported"]
    value_num: float | None = None
    value_text: str | None = Field(default=None, max_length=500)
    unit: str | None = None
    missing_reason: str | None = Field(default=None, max_length=60)


class SessionCompleteIn(BaseModel):
    status: Literal["completed", "interrupted", "abandoned"]
    interruptions: int = 0
    client_version: str = Field(default="web/0.1", max_length=40)
    observations: list[ObservationBody] = Field(default_factory=list, max_length=50)


class AmendIn(BaseModel):
    value_num: float | None = None
    value_text: str | None = Field(default=None, max_length=500)
    reason: str = Field(max_length=300)


class ReasonIn(BaseModel):
    reason: str = Field(max_length=300)


class ResolveIn(BaseModel):
    note: str = Field(max_length=500)
    decision: Literal["keep", "exclude"] = "keep"


class ResolveBatchIn(ResolveIn):
    ids: list[int] = Field(max_length=200)


class DraftIn(BaseModel):
    language: Lang = "en"


class DraftStatementIn(BaseModel):
    text: str = Field(max_length=1000)
    cites: list[str] = Field(default_factory=list, max_length=20)


class DraftReviewIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=500)
    statements: list[DraftStatementIn] | None = Field(default=None, max_length=20)


class LanguageIn(BaseModel):
    language: Lang


# ---- Reply shapes --------------------------------------------------------------------------------------------

def iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def grant_out(g: AccessGrant, db: Session) -> dict:
    return {"id": g.id, "owner": user_out(db.get(User, g.owner_id)), "grantee": user_out(db.get(User, g.grantee_id)),
            "purpose": g.purpose, "created_at": iso(g.created_at), "revoked_at": iso(g.revoked_at),
            "active": g.revoked_at is None}


def session_out(s: ActivitySession) -> dict:
    return {"id": s.id, "protocol_code": s.protocol_code, "protocol_version": s.protocol_version,
            "language": s.language, "device": s.device, "assisted": s.assisted, "assistance_note": s.assistance_note,
            "unwell_today": s.unwell_today, "interruptions": s.interruptions, "status": s.status,
            "started_at": iso(s.started_at), "ended_at": iso(s.ended_at)}


def evidence_out(e: Evidence) -> dict:
    return {"id": e.id, "participant_id": e.participant_id, "session_id": e.session_id, "kind": e.kind,
            "measure": e.measure, "value_num": e.value_num, "value_text": e.value_text, "unit": e.unit,
            "missing_reason": e.missing_reason, "protocol_code": e.protocol_code,
            "protocol_version": e.protocol_version, "producer_type": e.producer_type, "producer_id": e.producer_id,
            "producer_version": e.producer_version, "derived_from": e.derived_from, "quality": e.quality,
            "quality_reasons": e.quality_reasons, "status": e.status, "supersedes_id": e.supersedes_id,
            "superseded_by_id": e.superseded_by_id, "change_reason": e.change_reason,
            "recorded_at": iso(e.recorded_at)}


def draft_out(d: Draft) -> dict:
    """A refused draft never shows its text: only that it was refused, and why."""
    shown = d.status != "refused"
    return {"id": d.id, "participant_id": d.participant_id, "language": d.language, "status": d.status,
            "statements": d.statements if shown else [], "problems": d.problems,
            "facts": d.facts if shown else [], "provider": d.provider, "model": d.model,
            "validator_version": d.validator_version, "attempts": d.attempts, "created_by": d.created_by,
            "created_at": iso(d.created_at), "reviewed_by": d.reviewed_by, "reviewed_at": iso(d.reviewed_at),
            "review_note": d.review_note}


def care_item_out(i: CarePlanItem, db: Session) -> dict:
    return CP.item_out(db, i)


def message_out(m: FamilyMessage, db: Session) -> dict:
    return {"id": m.id, "sender": M.sender_name(db, m), "participant_id": m.participant_id, "text": m.text,
            "status": m.status, "created_at": iso(m.created_at), "sent_at": iso(m.sent_at), "read": m.read_at is not None}


def change_out(r) -> dict:
    d = r.as_dict()
    for w in ("baseline", "recent"):
        if d[w]:
            d[w] = {**d[w], "from": iso(d[w]["from"]), "to": iso(d[w]["to"])}
    return d


def review_out(r: ReviewItem) -> dict:
    return {"id": r.id, "participant_id": r.participant_id, "evidence_id": r.evidence_id, "session_id": r.session_id,
            "reason": r.reason, "raised_by": r.raised_by, "status": r.status, "decision": r.decision,
            "resolved_by": r.resolved_by,
            "resolution_note": r.resolution_note, "created_at": iso(r.created_at), "resolved_at": iso(r.resolved_at)}


# ---- App -----------------------------------------------------------------------------------------------------

def create_app(database_url: str | None = None, seed_demo: bool | None = None, serve_frontend: bool = True,
               demo_password: str | None = None, secure_cookies: bool | None = None,
               session_hours: float | None = None) -> FastAPI:
    app = FastAPI(title="IFHAS-NeuroTwin API", version="0.3.0",
                  description="Research prototype. Not a medical device. Synthetic demo data only.")
    app.state.db = Database(database_url or config.DATABASE_URL)
    app.state.settings = {
        "secure_cookies": config.SECURE_COOKIES if secure_cookies is None else secure_cookies,
        "session_hours": session_hours or config.SESSION_HOURS,
    }
    app.state.db.create_all()
    from .native_imaging import recover_interrupted
    with app.state.db.SessionLocal() as db:
        recover_interrupted(db)
    if config.SEED_DEMO if seed_demo is None else seed_demo:
        from .seed import ensure_demo_credentials, seed
        with app.state.db.SessionLocal() as db:
            seed(db)
            ensure_demo_credentials(db, demo_password or config.DEMO_PASSWORD)
    app.state.demo = bool(config.SEED_DEMO if seed_demo is None else seed_demo)
    app.state.get_llm = llm.get_client
    app.state.get_stt = llm.get_stt_client
    app.add_middleware(SafeRequestLog)
    app.add_middleware(ImagingRequestGuard)

    @app.exception_handler(S.Refused)
    async def _refused(_: Request, exc: S.Refused):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": app.version}

    # Sign-in, sign-out, account settings -----------------------------------------------------------------------
    app.include_router(auth_router)
    app.include_router(imaging_router)
    app.include_router(oasis2_router)
    app.include_router(agent_router)
    app.include_router(native_imaging_router)

    @app.get("/api/demo-accounts")
    def demo_accounts(request: Request, db: Session = Depends(get_db)):
        """Demo mode only: the synthetic accounts' usernames, so testers can sign in. Never real accounts."""
        if not request.app.state.demo:
            return []
        rows = db.scalars(select(User).where(User.is_demo.is_(True)).order_by(User.role, User.id))
        return [{"username": u.username, "display_name": u.display_name, "role": u.role, "language": u.language}
                for u in rows]

    @app.get("/api/me")
    def me(user: User = Depends(current_user)):
        return user_out(user, own=True)

    @app.put("/api/me/language")
    def set_language(body: LanguageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        u = db.get(User, user.id)
        u.language = body.language
        db.commit()
        return user_out(u, own=True)

    @app.get("/api/ai/status")
    def ai_status(_: User = Depends(current_user)):
        """Whether a model provider is configured. Names and booleans only."""
        return llm.status()

    @app.get("/api/voice/status")
    def voice_status(request: Request, _: User = Depends(current_user)):
        c = request.app.state.get_stt()
        return {"available": c is not None, "provider": c.provider if c else None}

    @app.post("/api/voice/transcribe")
    async def voice_transcribe(request: Request, language: str = "en", user: User = Depends(current_user),
                               db: Session = Depends(get_db)):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > V.MAX_BYTES:
            raise HTTPException(413, "That recording is too long. Keep it under a minute.")
        audio = await request.body()
        return V.transcribe(db, user, audio, request.headers.get("content-type", ""), language, request.app.state.get_stt())

    @app.get("/api/protocols")
    def list_protocols(_: User = Depends(current_user)):
        return [P.as_dict(p) for p in P.PROTOCOLS.values()]

    # Consent -------------------------------------------------------------------------------------------------
    @app.get("/api/consents")
    def my_consents(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            return []
        return [{**c, "at": iso(c["at"])} for c in S.consent_state(db, user.id).values()]

    @app.post("/api/consents")
    def set_consent(body: ConsentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        c = S.set_consent(db, user, body.scope, body.granted, body.language)
        return {**c, "at": iso(c["at"])}

    # Sharing -------------------------------------------------------------------------------------------------
    @app.get("/api/grants")
    def my_grants(user: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(AccessGrant).where(AccessGrant.owner_id == user.id).order_by(AccessGrant.id.desc()))
        return [grant_out(g, db) for g in rows]

    @app.get("/api/grants/candidates")
    def grant_candidates(user: User = Depends(current_user), db: Session = Depends(get_db)):
        """People a participant may share with. In the prototype: the demo family and clinician accounts."""
        if user.role != "participant":
            return []
        rows = db.scalars(select(User).where(User.role.in_(["family", "clinician"]), User.is_demo.is_(user.is_demo)))
        return [user_out(u) for u in rows]

    @app.post("/api/grants")
    def create_grant(body: GrantIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return grant_out(S.create_grant(db, user, body.grantee_id, body.purpose), db)

    @app.post("/api/grants/{grant_id}/revoke")
    def revoke_grant(grant_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return grant_out(S.revoke_grant(db, user, grant_id), db)

    # Activities ----------------------------------------------------------------------------------------------
    @app.post("/api/sessions")
    def start_session(body: SessionStartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        s = S.start_session(db, user, body.protocol_code, body.protocol_version, body.language, body.device,
                            body.assisted, body.assistance_note, body.unwell_today)
        return session_out(s)

    @app.post("/api/sessions/{session_id}/complete")
    def complete_session(session_id: int, body: SessionCompleteIn, user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
        obs = [Q.ObservationIn(**o.model_dump()) for o in body.observations]
        records = S.complete_session(db, user, session_id, body.status, body.interruptions, obs, body.client_version)
        return {"session": session_out(db.get(ActivitySession, session_id)),
                "evidence": [evidence_out(e) for e in records]}

    @app.get("/api/participants/{pid}/sessions")
    def list_sessions(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        require_evidence_access(db, user, pid)
        rows = db.scalars(select(ActivitySession).where(ActivitySession.participant_id == pid)
                          .order_by(ActivitySession.started_at.desc()))
        return [session_out(s) for s in rows]

    # Evidence ------------------------------------------------------------------------------------------------
    @app.get("/api/participants/{pid}/evidence")
    def list_evidence(pid: str, include_history: bool = False, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
        require_evidence_access(db, user, pid)
        q = select(Evidence).where(Evidence.participant_id == pid)
        if not include_history:
            q = q.where(Evidence.status != "amended")
        rows = db.scalars(q.order_by(Evidence.recorded_at.desc(), Evidence.id.desc())).all()
        if user.id != pid:
            S.audit(db, user.id, "evidence.viewed", pid, None)
            db.commit()
        return [evidence_out(e) for e in rows]

    @app.get("/api/evidence/{eid}")
    def get_evidence(eid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        e = db.get(Evidence, eid)
        if e is None:
            raise HTTPException(404, "Not found, or you do not have access.")
        require_evidence_access(db, user, e.participant_id)
        chain = []
        cur = e
        while cur.supersedes_id:
            cur = db.get(Evidence, cur.supersedes_id)
            chain.append(evidence_out(cur))
        session = db.get(ActivitySession, e.session_id) if e.session_id else None
        return {"evidence": evidence_out(e), "earlier_versions": chain,
                "session": session_out(session) if session else None,
                "protocol": P.as_dict(p) if (p := P.get(e.protocol_code or "", e.protocol_version or "")) else None}

    @app.post("/api/evidence/{eid}/amend")
    def amend(eid: int, body: AmendIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return evidence_out(S.amend_self_report(db, user, eid, body.value_num, body.value_text, body.reason))

    @app.post("/api/evidence/{eid}/withdraw")
    def withdraw(eid: int, body: ReasonIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return evidence_out(S.withdraw_evidence(db, user, eid, body.reason))

    # Review ("To check") -------------------------------------------------------------------------------------
    @app.get("/api/participants/{pid}/review-items")
    def list_review(pid: str, status: str = "open", user: User = Depends(current_user), db: Session = Depends(get_db)):
        require_evidence_access(db, user, pid)
        q = select(ReviewItem).where(ReviewItem.participant_id == pid)
        if status != "all":
            q = q.where(ReviewItem.status == status)
        return [review_out(r) for r in db.scalars(q.order_by(ReviewItem.created_at.desc()))]

    @app.post("/api/review-items/{rid}/resolve")
    def resolve(rid: int, body: ResolveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return review_out(S.resolve_review(db, user, rid, body.note, body.decision))

    @app.post("/api/review-items/resolve-batch")
    def resolve_batch(body: ResolveBatchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return [review_out(r) for r in S.resolve_reviews(db, user, body.ids, body.note, body.decision)]

    @app.get("/api/participants/{pid}/report")
    def report(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        require_evidence_access(db, user, pid)
        r = S.build_report(db, user, pid)
        r["generated_at"] = iso(r["generated_at"])
        r["period"] = {k: iso(v) for k, v in r["period"].items()}
        for m in r["measures"]:
            m["first"], m["last"] = iso(m["first"]), iso(m["last"])
            m["values"] = [{**v, "at": iso(v["at"])} for v in m["values"]]
        r["review"] = {k: [review_out(i) for i in v] for k, v in r["review"].items()}
        for c in r["change"]:
            for w in ("baseline", "recent"):
                if c[w]:
                    c[w] = {**c[w], "from": iso(c[w]["from"]), "to": iso(c[w]["to"])}
        return r

    @app.get("/api/participants/{pid}/change")
    def change(pid: str, include_doubtful: bool = False, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
        """Within-person change estimates. Clinicians only: an estimate is read beside its records by a person
        qualified to interpret it, never shown to the participant or family on its own."""
        if user.role != "clinician":
            raise HTTPException(404, "Not found, or you do not have access.")
        require_evidence_access(db, user, pid)
        rows = db.scalars(select(Evidence).where(Evidence.participant_id == pid)).all()
        out = [change_out(r) for r in C.compare_all(rows, include_doubtful)]
        S.audit(db, user.id, "change.computed", pid, C.METHOD)
        db.commit()
        return out

    # Model-written summary drafts (clinicians only) ----------------------------------------------------------
    def _clinician_for(db: Session, user: User, pid: str) -> None:
        if user.role != "clinician":
            raise HTTPException(404, "Not found, or you do not have access.")
        require_evidence_access(db, user, pid)

    @app.get("/api/participants/{pid}/drafts")
    def list_drafts(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        _clinician_for(db, user, pid)
        rows = db.scalars(select(Draft).where(Draft.participant_id == pid).order_by(Draft.id.desc()).limit(20))
        return [draft_out(d) for d in rows]

    @app.post("/api/participants/{pid}/drafts")
    def create_draft(pid: str, body: DraftIn, request: Request, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
        _clinician_for(db, user, pid)
        return draft_out(D.generate(db, user, pid, body.language, request.app.state.get_llm()))

    @app.post("/api/drafts/{did}/review")
    def review_draft(did: int, body: DraftReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        d = db.get(Draft, did)
        if d is None:
            raise HTTPException(404, "Not found, or you do not have access.")
        _clinician_for(db, user, d.participant_id)
        statements = [x.model_dump() for x in body.statements] if body.statements is not None else None
        return draft_out(D.review(db, user, d, body.decision, body.note, statements))

    # Family messages: write, preview, send ----------------------------------------------------------------------
    @app.post("/api/family/messages")
    def draft_message(body: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return message_out(M.make_draft(db, user, body.participant_id, body.text), db)

    @app.post("/api/family/messages/{mid}/send")
    def send_message(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return message_out(M.send(db, user, mid), db)

    @app.post("/api/family/messages/{mid}/discard")
    def discard_message(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return message_out(M.discard(db, user, mid), db)

    @app.get("/api/family/messages")
    def my_written_messages(participant_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return [message_out(m, db) for m in M.written_by(db, user, participant_id)]

    @app.get("/api/messages")
    def my_inbox(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        return [message_out(m, db) for m in M.inbox(db, user)]

    @app.post("/api/messages/{mid}/read")
    def read_message(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        M.mark_read(db, user, mid)
        return {"ok": True}

    @app.post("/api/messages/{mid}/hide")
    def hide_message(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        M.hide(db, user, mid)
        return {"ok": True}

    # Care plan and reminders ---------------------------------------------------------------------------------
    @app.get("/api/participants/{pid}/care-plan")
    def clinician_care_plan(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        _clinician_for(db, user, pid)
        return CP.clinician_view(db, pid)

    @app.post("/api/participants/{pid}/care-plan")
    def add_care_item(pid: str, body: CarePlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        _clinician_for(db, user, pid)
        item = CP.add_item(db, user, pid, **body.model_dump())
        return care_item_out(item, db)

    @app.post("/api/care-plan/{item_id}/stop")
    def stop_care_item(item_id: int, body: CarePlanStopIn, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
        item = db.get(CarePlanItem, item_id)
        if item is None:
            raise HTTPException(404, "Not found, or you do not have access.")
        _clinician_for(db, user, item.participant_id)
        return care_item_out(CP.stop_item(db, user, item, body.note), db)

    def _plan_for_clinician(db: Session, user: User, plan_id: int):
        plan = db.get(CarePlan, plan_id)
        if plan is None:
            raise HTTPException(404, "Not found, or you do not have access.")
        _clinician_for(db, user, plan.participant_id)
        return plan

    @app.post("/api/care-plans/{plan_id}/send")
    def send_care_plan(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CP.plan_out(db, CP.send_plan(db, user, _plan_for_clinician(db, user, plan_id)))

    @app.post("/api/care-plans/{plan_id}/recall")
    def recall_care_plan(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CP.plan_out(db, CP.recall_plan(db, user, _plan_for_clinician(db, user, plan_id)))

    @app.get("/api/care-plan/awaiting")
    def plans_awaiting_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        return CP.awaiting(db, user)

    @app.post("/api/care-plans/{plan_id}/respond")
    def respond_to_care_plan(plan_id: int, body: PlanResponseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        plan = db.get(CarePlan, plan_id)
        if plan is None or user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        CP.respond(db, user, plan, body.response, body.note)
        return {"ok": True, "status": plan.status}

    @app.get("/api/care-plan/today")
    def my_reminders(day: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        d = CP.reply_day(db, user, day)
        return {"day": d.isoformat(), "timezone": CP.tz_name(db, user),
                "items": [{**care_item_out(i, db), "reply": st["reply"], "snoozed_until": CP._iso(st["snoozed_until"]), "difficulty": st["difficulty"]}
                          for i, st in CP.todays(db, user, d)]}

    @app.post("/api/care-plan/{item_id}/reply")
    def reply_to_reminder(item_id: int, body: CarePlanReplyIn, user: User = Depends(current_user),
                          db: Session = Depends(get_db)):
        item = db.get(CarePlanItem, item_id)
        if item is None or user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        _, dup = CP.reply(db, user, item, CP.reply_day(db, user, body.day), body.reply, idem_key=body.idem_key,
                          snooze_minutes=body.snooze_minutes, reason=body.reason, note=body.note)
        return {"ok": True, "duplicate": dup}

    @app.get("/api/care-plan/history")
    def my_history(days: int = 14, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        return CP.history(db, user, days)

    @app.get("/api/notifications")
    def my_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CP.notifications(db, user)

    @app.post("/api/notifications/{nid}/read")
    def read_notification(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        CP.mark_read(db, user, nid)
        return {"ok": True}

    @app.post("/api/plan-responses/{rid}/review")
    def review_plan_response(rid: int, body: CarePlanStopIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(PlanResponse, rid)
        if row is None:
            raise HTTPException(404, "Not found, or you do not have access.")
        _clinician_for(db, user, row.participant_id)
        r = CP.review_response(db, user, rid, body.note)
        return {"ok": True, "reviewed_at": CP._iso(r.reviewed_at)}

    @app.post("/api/participants/{pid}/care-plan/suggest")
    def suggest_fields(pid: str, body: SuggestIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        """Fields read from the clinician's own text by fixed rules, with flags. Nothing is saved; the clinician decides."""
        _clinician_for(db, user, pid)
        text = " ".join(filter(None, [body.text_en, body.text_ar]))
        fields = EX.propose(text)
        return {"source": "rules", "fields": fields, "flags": EX.check(text, fields)}

    @app.post("/api/assistant/message")
    def assistant_message(body: AssistantIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return AS.message(db, user, body.text)

    @app.post("/api/assistant/confirm")
    def assistant_confirm(body: AssistantConfirmIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return AS.confirm(db, user, body.confirmation_id)

    @app.post("/api/assistant/cancel")
    def assistant_cancel(body: AssistantConfirmIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return AS.cancel(db, user, body.confirmation_id)

    @app.get("/api/assistant/history")
    def assistant_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
        return AS.history(db, user)

    @app.delete("/api/assistant/history")
    def assistant_clear(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        return {"cleared": AS.clear(db, user)}

    @app.put("/api/assistant/memory")
    def assistant_memory(body: MemoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        return {"memory": AS.set_memory(db, user, body.enabled)}

    # Concern reports ------------------------------------------------------------------------------------------
    @app.get("/api/concerns/info")
    def concern_info(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "participant":
            raise HTTPException(404, "Not found, or you do not have access.")
        return {"monitoring_hours": CN.monitoring_hours(), "recipients": CN.recipients(db, user)}

    @app.get("/api/concerns")
    def my_concerns(user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.mine(db, user)

    @app.post("/api/concerns")
    def create_concern(body: ConcernIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.out(db, CN.create(db, user, body.topic, body.since, body.text))

    @app.put("/api/concerns/{rid}")
    def edit_concern(rid: int, body: ConcernIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.out(db, CN.edit(db, user, rid, body.topic, body.since, body.text))

    @app.post("/api/concerns/{rid}/send")
    def send_concern(rid: int, body: ConcernSendIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.out(db, CN.send(db, user, rid, body.rev, body.recipient_id))

    @app.post("/api/concerns/{rid}/withdraw")
    def withdraw_concern(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.out(db, CN.withdraw(db, user, rid))

    @app.get("/api/concerns/inbox")
    def concern_inbox(user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.inbox(db, user)

    @app.post("/api/concerns/{rid}/acknowledge")
    def acknowledge_concern(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.out(db, CN.acknowledge(db, user, rid), True)

    @app.post("/api/concerns/{rid}/review")
    def review_concern(rid: int, body: CarePlanStopIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.out(db, CN.review(db, user, rid, body.note), True)

    @app.post("/api/concerns/{rid}/close")
    def close_concern(rid: int, body: CarePlanStopIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return CN.out(db, CN.close(db, user, rid, body.note), True)

    @app.get("/api/emergency/config")
    def emergency_config(user: User = Depends(current_user), db: Session = Depends(get_db)):
        return EM.config(db, user)

    @app.put("/api/emergency/trusted")
    def emergency_trusted(body: TrustedIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return EM.set_trusted(db, user, body.name, body.phone)

    @app.delete("/api/emergency/trusted")
    def emergency_trusted_clear(user: User = Depends(current_user), db: Session = Depends(get_db)):
        EM.clear_trusted(db, user)
        return {"ok": True}

    @app.get("/api/me/preferences")
    def my_preferences(user: User = Depends(current_user), db: Session = Depends(get_db)):
        return {"timezone": CP.tz_name(db, user)}

    @app.put("/api/me/preferences")
    def set_my_preferences(body: TimezoneIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return {"timezone": CP.set_timezone(db, user, body.timezone)}

    @app.get("/api/participants/{pid}/audit")
    def list_audit(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        require_evidence_access(db, user, pid)
        rows = db.scalars(select(AuditEvent).where(AuditEvent.participant_id == pid)
                          .order_by(AuditEvent.id.desc()).limit(200))
        return [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "target": a.target, "at": iso(a.at)}
                for a in rows]

    # Clinician and family views ------------------------------------------------------------------------------
    @app.get("/api/clinician/participants")
    def clinician_participants(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "clinician":
            raise HTTPException(403, "For clinicians only.")
        grants = db.scalars(select(AccessGrant).where(AccessGrant.grantee_id == user.id,
                                                      AccessGrant.purpose == "clinical_review",
                                                      AccessGrant.revoked_at.is_(None)))
        out = []
        for g in grants:
            p = db.get(User, g.owner_id)
            open_items = db.query(ReviewItem).filter(ReviewItem.participant_id == p.id,
                                                     ReviewItem.status == "open").count()
            last = db.scalar(select(ActivitySession.started_at).where(ActivitySession.participant_id == p.id)
                             .order_by(ActivitySession.started_at.desc()).limit(1))
            out.append({**user_out(p), "shared_since": iso(g.created_at), "open_items": open_items,
                        "last_activity": iso(last)})
        return out

    @app.get("/api/family/shared")
    def family_shared(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role != "family":
            raise HTTPException(403, "For family members only.")
        return [{**e, "since": iso(e["since"]), "ended_at": iso(e["ended_at"]),
                 "recent": [{**r, "at": iso(r["at"])} for r in e["recent"]]} for e in S.family_view(db, user)]

    @app.get("/api/family/imaging-summaries")
    def family_imaging(user: User = Depends(current_user), db: Session = Depends(get_db)):
        """Scan-comparison summaries a clinician released to this family member. Re-checked on every request."""
        if user.role != "family":
            raise HTTPException(403, "For family members only.")
        from . import agent_family
        return agent_family.family_summaries(db, user)

    # The built web app, when present -------------------------------------------------------------------------
    dist = config.FRONTEND_DIST
    if serve_frontend and dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            f = (dist / path).resolve()
            if path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# Run with:  uvicorn app.main:create_app --factory
