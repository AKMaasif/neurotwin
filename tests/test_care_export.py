from app.db import Audit, Grant, Patient, Record
from tests.conftest import sign_in

PATH = "/api/patients/patient-demo/care-summary/export"


def test_export_is_scoped_projected_and_audited(client, database):
    with database() as db:
        plan = db.get(Record, "plan-demo")
        plan.payload = plan.payload | {
            "clinician_secret": "PRIVATE-PLAN-NOTE",
            "source_review_required": True,
        }
        for kind in ["case", "draft", "model", "document", "companion_memory"]:
            db.add(
                Record(
                    patient_id="patient-demo",
                    kind=kind,
                    status="draft",
                    payload={"text": "PRIVATE-EXCLUDED-" + kind},
                )
            )
        db.add(
            Record(
                id="hidden-plan",
                patient_id="patient-demo",
                kind="plan",
                status="draft",
                payload={"title": "PRIVATE-DRAFT"},
            )
        )
        db.add(
            Record(
                patient_id="patient-demo",
                kind="task",
                status="pending",
                payload={"plan_id": "hidden-plan", "title": "PRIVATE-DRAFT-TASK"},
            )
        )
        db.add(
            Record(
                patient_id="patient-demo",
                kind="help",
                status="requested",
                payload={
                    "sender_id": "clinician",
                    "recipient_id": "family",
                    "text": "PRIVATE-OTHER-HELP",
                },
            )
        )
        db.add(
            Record(
                patient_id="patient-demo",
                kind="help",
                status="requested",
                payload={
                    "sender_id": "participant",
                    "recipient_id": "family",
                    "text": "My visible request",
                },
            )
        )
        db.commit()
    sign_in(client)
    response = client.post(PATH)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["schema_version"] == "neurotwin.care-summary.v1"
    assert data["patient"]["id"] == "patient-demo"
    assert "PRIVATE-" not in response.text
    assert "My visible request" in response.text
    plan = next(row for row in data["records"] if row["id"] == "plan-demo")
    assert plan["payload"]["source_review_required"] is True
    assert "clinician_secret" not in plan["payload"]
    assert data["clinical_validation"] is False
    assert data["scope"]["excluded"]
    assert response.headers["cache-control"] == "no-store"
    assert "attachment;" in response.headers["content-disposition"]
    with database() as db:
        audit = db.query(Audit).filter_by(action="care_summary.exported").one()
        assert "My visible request" not in str(audit.detail)


def test_roles_patient_csrf_and_revocation(client, database):
    assert client.post(PATH).status_code == 401
    for role in ["family", "clinician", "other"]:
        sign_in(client, role)
        assert client.post(PATH).status_code == 403
    sign_in(client)
    assert client.post(PATH.replace("patient-demo", "patient-other")).status_code == 403
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post(PATH).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    with database() as db:
        db.query(Grant).filter_by(
            user_id="participant", patient_id="patient-demo"
        ).one().active = False
        db.commit()
    assert client.post(PATH).status_code == 403


def test_summary_only_grant_and_extra_review_scope_do_not_expand_export(
    client, database
):
    sign_in(client)
    with database() as db:
        grant = (
            db.query(Grant)
            .filter_by(user_id="participant", patient_id="patient-demo")
            .one()
        )
        grant.scopes = ["summary", "review"]
        db.add(
            Record(
                patient_id="patient-demo",
                kind="case",
                status="reviewed",
                payload={"text": "PRIVATE-CLINICAL"},
            )
        )
        db.commit()
    data = client.post(PATH).json()
    assert data["records"] == []
    assert "PRIVATE-CLINICAL" not in str(data)


def test_real_data_gate_and_oversize_fail_closed(client, database):
    sign_in(client)
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = False
        db.commit()
    assert client.post(PATH).status_code == 403
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = True
        db.add_all(
            [
                Record(
                    patient_id="patient-demo",
                    kind="task",
                    status="pending",
                    payload={"plan_id": "plan-demo", "title": "Synthetic"},
                )
                for _ in range(1001)
            ]
        )
        db.commit()
    assert client.post(PATH).status_code == 422


def test_unknown_nested_payload_fields_are_excluded(client, database):
    sign_in(client)
    with database() as db:
        task = db.get(Record, "task-01")
        task.payload = task.payload | {
            "response": {
                "response": "completed",
                "at": "2026-11-07T00:00:00Z",
                "private_note": "PRIVATE-RESPONSE",
            }
        }
        db.commit()
    response = client.post(PATH)
    assert response.status_code == 200
    assert "PRIVATE-RESPONSE" not in response.text
