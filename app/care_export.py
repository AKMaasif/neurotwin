"""Participant-only download of an explicit, limited care-summary projection."""

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .db import Audit, Grant, Record, User, get_db, now
from .security import authenticated, authorize

router = APIRouter(prefix="/api/patients/{pid}/care-summary")
FIELDS = {
    "plan": {
        "title",
        "instructions",
        "signed_by",
        "signed_at",
        "source_review_required",
    },
    "task": {
        "title",
        "period",
        "time",
        "steps",
        "plan_id",
        "plan_version",
        "evidence_type",
        "responded_by",
        "responded_at",
        "scheduled_at",
    },
    "help": {"text", "sender_id", "recipient_id", "delivery"},
    "preference": {"text_size"},
}


@router.post("/export")
def export(pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    patient = authorize(db, u, pid, "summary")
    if u.role != "participant" or not patient.synthetic:
        raise HTTPException(
            403,
            "Care-summary export is enabled only for synthetic participant workspaces",
        )
    grant = db.query(Grant).filter_by(user_id=u.id, patient_id=pid, active=True).one()
    kinds = []
    for scope, records in [
        ("tasks", ["plan", "task"]),
        ("help", ["help"]),
        ("preferences", ["preference"]),
    ]:
        if scope in grant.scopes:
            kinds.extend(records)
    rows = (
        db.query(Record)
        .filter(Record.patient_id == pid, Record.kind.in_(kinds))
        .order_by(Record.created_at, Record.id)
        .limit(1001)
        .all()
    )
    if len(rows) > 1000:
        raise HTTPException(
            422,
            "Care summary exceeds the export limit; ask your care team for a partitioned export",
        )
    approved = {r.id for r in rows if r.kind == "plan" and r.status == "approved"}
    included = []
    for row in rows:
        if row.kind == "plan" and row.id not in approved:
            continue
        if row.kind == "task" and (
            row.payload.get("plan_id") not in approved
            or row.status == "superseded"
            or row.payload.get("is_routine_template")
        ):
            continue
        if row.kind == "help" and u.id not in [
            row.payload.get("sender_id"),
            row.payload.get("recipient_id"),
        ]:
            continue
        included.append(
            {
                "id": row.id,
                "kind": row.kind,
                "version": row.version,
                "status": row.status,
                "created_at": row.created_at,
                "payload": {
                    key: row.payload[key]
                    for key in sorted(FIELDS[row.kind])
                    if key in row.payload
                },
            }
        )
    result = {
        "schema_version": "neurotwin.care-summary.v1",
        "exported_at": now(),
        "patient": {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "region": patient.region,
            "synthetic": patient.synthetic,
        },
        "records": included,
        "clinical_validation": False,
        "scope": {
            "included": "Approved plans, linked tasks excluding superseded/templates, help requests involving this participant, and text-size preference, subject to granted scopes.",
            "excluded": [
                "clinical notes/cases",
                "drafts",
                "model outputs",
                "documents",
                "messages and attachments",
                "companion memory",
                "research sessions",
                "device events",
                "audit logs",
                "superseded plans/tasks",
                "complete medical-record history",
            ],
            "interpretation": "Recorded states only. Participant responses do not prove medication administration or clinical stability. Check source-review holds with your care team.",
        },
    }
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="care_summary.exported",
            detail={
                "counts": dict(Counter(row["kind"] for row in included)),
                "schema_version": result["schema_version"],
            },
        )
    )
    db.commit()
    return JSONResponse(
        result,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="neurotwin-care-summary.json"',
        },
    )
