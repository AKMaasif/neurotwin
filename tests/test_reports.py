import json

import pytest
from conftest import sign_in

from app.db import Audit, Grant, Patient, Record, Routine, RoutineOccurrence, User
from app.security import password_hash

BASE = "/api/patients/patient-demo/reports"
END = "2026-11-06"


@pytest.fixture(autouse=True)
def report_clock(monkeypatch):
    monkeypatch.setattr("app.reports.now", lambda: "2026-11-06T18:00:00+00:00")


def data(database):
    with database() as db:
        for i, status, when in [
            ("task-01", "completed", "2026-11-01T20:01:00+00:00"),
            ("task-02", "unconfirmed", "2026-10-31T19:59:00+00:00"),
        ]:
            r = db.get(Record, i)
            r.created_at = when
            r.status = status
        db.add(
            Record(
                id="old",
                patient_id="patient-demo",
                kind="task",
                status="skipped",
                created_at="2026-10-25T12:00:00+00:00",
                payload={"plan_id": "plan-demo", "title": "Older task"},
            )
        )
        db.add(
            Record(
                id="template",
                patient_id="patient-demo",
                kind="task",
                status="pending",
                created_at="2026-11-02T12:00:00+00:00",
                payload={"plan_id": "plan-demo", "is_routine_template": True},
            )
        )
        db.add(
            Record(
                id="private-doc",
                patient_id="patient-demo",
                kind="document",
                status="reviewed",
                payload={
                    "candidates": [
                        {
                            "id": "fact",
                            "status": "verified",
                            "quote": "PRIVATE DOCUMENT",
                            "reviewed_at": "2026-11-02T12:00:00+00:00",
                        }
                    ]
                },
            )
        )
        db.add(
            Record(
                id="private-memory",
                patient_id="patient-demo",
                kind="companion_memory",
                status="active",
                payload={"text": "PRIVATE MEMORY"},
            )
        )
        db.add(
            Record(
                id="measurement",
                patient_id="patient-demo",
                kind="observation",
                status="poor",
                created_at="2026-11-02T12:00:00+00:00",
                payload={"protocol": "research", "value": 4, "mode": "self"},
            )
        )
        db.add(
            Audit(
                patient_id="patient-demo",
                actor="participant",
                action="task.response",
                detail={"record": "task-01", "response": "completed"},
                created_at="2026-11-01T20:01:00+00:00",
            )
        )
        db.commit()


def weekly(client, **kw):
    return client.get(BASE + "/weekly", params={"end_date": END, **kw})


def snapshot(client, **kw):
    response = client.post(BASE + "/snapshots", json={"end_date": END, **kw})
    assert response.status_code == 200, response.text
    return response.json()


def review(client, r, **kw):
    return client.post(
        BASE + f"/snapshots/{r['id']}/review",
        json={"expected_version": r["version"], "decision": "approve", **kw},
    )


def test_weekly_timezone_cohorts_no_invented_denominator(client, database):
    data(database)
    sign_in(client, "family")
    r = weekly(client).json()
    assert r["denominator"] == 2
    assert r["counts"]["completed"] == r["counts"]["unconfirmed"] == 1
    assert r["daily"][0]["date"] == "2026-10-31"
    assert (
        next(d for d in r["daily"] if d["date"] == "2026-11-02")["counts"]["completed"]
        == 1
    )
    assert r["data_quality"]["expected_activities"] is None
    assert r["data_quality"]["dates_without_recorded_activities"] == 5
    assert r["trend"][-2]["counts"]["skipped"] == 1
    assert len(r["timeline"]) == 1
    assert "PRIVATE" not in json.dumps(r)
    assert r["clinical"] is None
    assert weekly(client, timezone="Europe/Invalid").status_code == 422
    assert weekly(client, end_date="2026-11-07").status_code == 422
    assert client.get("/api/patients/patient-other/reports/weekly").status_code == 403
    assert weekly(client, audience="clinical").status_code == 403


def test_clinical_projection_and_approval_visibility(client, database):
    data(database)
    sign_in(client, "clinician")
    r = weekly(client, audience="clinical").json()
    assert r["clinical"]["research_measurements"][0]["quality"] == "poor"
    assert r["clinical"]["verified_source_facts"][0]["quote"] == "PRIVATE DOCUMENT"
    assert "PRIVATE MEMORY" not in json.dumps(r)
    clinical = snapshot(client)
    assert review(client, clinical).status_code == 200
    family = snapshot(client, audience="family", recipient_id="family")
    sign_in(client, "family")
    assert client.get(BASE + "/snapshots").json() == []
    assert review(client, family).status_code == 403
    sign_in(client, "clinician")
    approved = review(client, family, note="PRIVATE CLINICIAN NOTE")
    assert approved.status_code == 200
    assert review(client, family).status_code == 409
    sign_in(client, "family")
    shared = client.get(BASE + "/snapshots").json()
    assert len(shared) == 1
    assert "PRIVATE" not in json.dumps(shared)
    assert shared[0]["status"] == "approved"
    # A frozen snapshot keeps its generation-time evidence after a late response.
    with database() as db:
        db.get(Record, "task-02").status = "completed"
        db.commit()
    assert (
        client.get(BASE + "/snapshots").json()[0]["snapshot"]["counts"]["unconfirmed"]
        == 1
    )
    assert weekly(client).json()["counts"]["completed"] == 2
    with database() as db:
        g = db.query(Grant).filter_by(user_id="family", patient_id="patient-demo").one()
        g.scopes = ["summary"]
        db.commit()
    assert client.get(BASE + "/snapshots").json() == []
    assert weekly(client).json()["denominator"] == 0


def test_stale_snapshot_rejected_and_rejection_allowed(client, database):
    data(database)
    sign_in(client, "clinician")
    r = snapshot(client)
    with database() as db:
        task = db.get(Record, "task-01")
        task.status = "deferred"
        task.version += 1
        db.commit()
    assert review(client, r).status_code == 409
    assert review(client, r, decision="reject").status_code == 200


def test_recipient_bound_support_and_revocation(client, database):
    data(database)
    with database() as db:
        db.add(
            User(
                id="family2",
                name="Relative",
                role="family",
                org="demo",
                password_hash=password_hash("test-password-not-for-deployment"),
            )
        )
        db.flush()
        db.add(
            Grant(
                user_id="family2",
                patient_id="patient-demo",
                scopes=["summary", "tasks", "help"],
            )
        )
        for target in ["family", "family2"]:
            db.add(
                Record(
                    id="help-" + target,
                    patient_id="patient-demo",
                    kind="help",
                    status="requested",
                    created_at="2026-11-02T12:00:00+00:00",
                    payload={"sender_id": "participant", "recipient_id": target},
                )
            )
            db.add(
                Audit(
                    patient_id="patient-demo",
                    actor="participant",
                    action="help.requested",
                    detail={"record": "help-" + target},
                    created_at="2026-11-02T12:00:00+00:00",
                )
            )
        db.commit()
    sign_in(client, "clinician")
    r = snapshot(client, audience="family", recipient_id="family")
    assert len(r["snapshot"]["help"]) == 1
    assert r["snapshot"]["help"][0]["id"] == "help-family"
    assert "help-family2" not in json.dumps(r)
    assert review(client, r).status_code == 200
    sign_in(client, "family2")
    assert client.get(BASE + "/snapshots").json() == []
    assert weekly(client, recipient_id="family").status_code == 403
    sign_in(client, "family")
    assert len(client.get(BASE + "/snapshots").json()) == 1
    with database() as db:
        db.query(Grant).filter_by(
            user_id="family", patient_id="patient-demo"
        ).one().active = False
        db.commit()
    assert client.get(BASE + "/snapshots").status_code == 403


@pytest.mark.parametrize(
    "mode", ["valid", "hallucination", "duplicate", "source_change", "revocation"]
)
def test_ai_exact_fact_validation_and_inflight_checks(
    client, database, monkeypatch, mode
):
    data(database)
    sign_in(client, "clinician")
    r = snapshot(client, audience="family", recipient_id="family")

    async def fake(provider, model, prompt, schema):
        assert provider == "meta"
        assert "PRIVATE" not in prompt
        fact = r["snapshot"]["facts"][0]
        q = {"source_id": fact["id"], "quote": fact["text"]}
        if mode == "hallucination":
            q["quote"] = "Patient cognition is declining"
        if mode in {"source_change", "revocation"}:
            with database() as db:
                if mode == "source_change":
                    db.get(Record, "task-01").status = "skipped"
                else:
                    db.query(Grant).filter_by(
                        user_id="family", patient_id="patient-demo"
                    ).one().active = False
                db.commit()
        return {"observations": [q, q] if mode == "duplicate" else [q]}

    monkeypatch.setattr("app.reports.gateway.structured", fake)
    result = client.post(
        BASE + f"/snapshots/{r['id']}/summarize", json={"expected_version": 1}
    )
    expected = {
        "valid": 200,
        "hallucination": 502,
        "duplicate": 502,
        "source_change": 409,
        "revocation": 403,
    }[mode]
    assert result.status_code == expected, result.text
    with database() as db:
        saved = db.get(Record, r["id"])
        assert saved.status == ("awaiting_review" if mode == "valid" else "draft")
        assert saved.version == (2 if mode == "valid" else 1)


def test_empty_week_caps_and_non_synthetic_ai(client, database, monkeypatch):
    sign_in(client, "clinician")
    empty = weekly(client, end_date="2026-01-01", audience="clinical").json()
    assert empty["denominator"] == 0
    assert empty["data_quality"]["dates_without_recorded_activities"] == 7
    assert all(w["denominator"] == 0 for w in empty["trend"])
    r = snapshot(client)
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = False
        db.commit()
    assert (
        client.post(
            BASE + f"/snapshots/{r['id']}/summarize", json={"expected_version": 1}
        ).status_code
        == 403
    )
    monkeypatch.setattr("app.reports.LIMIT", 1)
    assert weekly(client).status_code == 422


def test_dst_week_uses_local_midnights(client, database):
    with database() as db:
        db.add(
            Audit(
                patient_id="patient-demo",
                actor="participant",
                action="task.response",
                detail={"record": "task-01", "response": "completed"},
                created_at="2026-11-02T04:59:00+00:00",
            )
        )
        db.add(
            Audit(
                patient_id="patient-demo",
                actor="participant",
                action="task.response",
                detail={"record": "task-01", "response": "deferred"},
                created_at="2026-11-02T05:00:00+00:00",
            )
        )
        db.commit()
    sign_in(client)
    r = weekly(client, end_date="2026-11-01", timezone="America/New_York").json()
    assert len(r["timeline"]) == 1
    assert r["timeline"][0]["response"] == "completed"


def test_scheduled_date_templates_cancellations_and_historical_plans(client, database):
    data(database)
    with database() as db:
        plan = db.get(Record, "plan-demo")
        plan.status = "superseded"
        db.add(
            Routine(
                id="r",
                patient_id="patient-demo",
                owner_id="participant",
                template_id="template",
                status="paused",
                payload={},
            )
        )
        for key, status, due in [
            ("scheduled", "pending", "2026-11-03T08:00:00+00:00"),
            ("future", "pending", "2026-11-06T20:00:00+00:00"),
            ("cancelled", "cancelled", "2026-11-04T08:00:00+00:00"),
        ]:
            db.add(
                Record(
                    id=key,
                    patient_id="patient-demo",
                    kind="task",
                    status=status,
                    created_at="2026-01-01T00:00:00+00:00",
                    payload={"plan_id": "plan-demo", "title": key},
                )
            )
        db.flush()
        for key, due in [
            ("scheduled", "2026-11-03T08:00:00+00:00"),
            ("future", "2026-11-06T20:00:00+00:00"),
            ("cancelled", "2026-11-04T08:00:00+00:00"),
        ]:
            db.add(
                RoutineOccurrence(
                    id=key,
                    routine_id="r",
                    task_id=key,
                    routine_version=1,
                    local_date=due[:10],
                    scheduled_at=due,
                    reminder_at=due,
                )
            )
        db.commit()
    sign_in(client, "family")
    r = weekly(client).json()
    assert r["denominator"] == 3
    assert sum(d["excluded"] for d in r["daily"]) == 1
    activity = next(t for t in r["activities"] if t["id"] == "scheduled")
    assert activity["date"] == "2026-11-03"
    assert activity["date_basis"] == "scheduled"
    assert all(
        t["id"] not in {"template", "future", "cancelled"} for t in r["activities"]
    )


def test_timeline_truncation_is_explicit(client, database):
    with database() as db:
        db.add_all(
            [
                Audit(
                    patient_id="patient-demo",
                    actor="participant",
                    action="task.response",
                    detail={"record": "task-01", "response": "completed"},
                    created_at="2026-11-01T12:00:00+00:00",
                )
                for _ in range(205)
            ]
        )
        db.commit()
    sign_in(client)
    r = weekly(client).json()
    assert r["timeline_total"] == 205
    assert len(r["timeline"]) == 200
    assert r["timeline_truncated"] is True
