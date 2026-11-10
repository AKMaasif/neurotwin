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
from . import protocols as P
from . import quality as Q
from . import services as S
from .db import Database
from .logs import SafeRequestLog
from .models import AccessGrant, ActivitySession, AuditEvent, Evidence, ReviewItem, User
from .auth import router as auth_router
from .auth import user_out
from .security import current_user, get_db, require_evidence_access

Lang = Literal["en", "ar"]


# ---- Request bodies ------------------------------------------------------------------------------------------

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
    app = FastAPI(title="IFHAS-NeuroTwin API", version="0.1.0",
                  description="Research prototype. Not a medical device. Synthetic demo data only.")
    app.state.db = Database(database_url or config.DATABASE_URL)
    app.state.settings = {
        "secure_cookies": config.SECURE_COOKIES if secure_cookies is None else secure_cookies,
        "session_hours": session_hours or config.SESSION_HOURS,
    }
    app.state.db.create_all()
    if config.SEED_DEMO if seed_demo is None else seed_demo:
        from .seed import ensure_demo_credentials, seed
        with app.state.db.SessionLocal() as db:
            seed(db)
            ensure_demo_credentials(db, demo_password or config.DEMO_PASSWORD)
    app.state.demo = bool(config.SEED_DEMO if seed_demo is None else seed_demo)
    app.add_middleware(SafeRequestLog)

    @app.exception_handler(S.Refused)
    async def _refused(_: Request, exc: S.Refused):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": app.version}

    # Sign-in, sign-out, account settings -----------------------------------------------------------------------
    app.include_router(auth_router)

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
