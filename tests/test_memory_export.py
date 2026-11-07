import datetime as dt

from conftest import sign_in

from app.db import Audit, Grant, Record

BASE = "/api/patients/patient-demo/companion/memory"


def test_export_only_retained_memory_and_audits_without_text(client, database):
    sign_in(client)
    assert (
        client.post(BASE, json={"expected_version": 0, "enabled": True}).status_code
        == 200
    )
    with database() as db:
        row = db.query(Record).filter_by(kind="companion_memory").one()
        row.payload = row.payload | {
            "history": [
                {
                    "user": "expired private text",
                    "assistant": "old",
                    "at": (
                        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)
                    ).isoformat(),
                },
                {
                    "user": "retained private text",
                    "assistant": "current",
                    "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                },
            ]
        }
        db.commit()
    result = client.post(BASE + "/export")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert "attachment;" in result.headers["content-disposition"]
    data = result.json()
    assert data["schema_version"] == "neurotwin.companion-memory.v1"
    assert data["patient_id"] == "patient-demo"
    assert len(data["memory"]["history"]) == 1
    assert data["memory"]["history"][0]["user"] == "retained private text"
    assert "expired private text" not in result.text
    assert "records" not in data and "csrf" not in data
    with database() as db:
        audit = db.query(Audit).filter_by(action="companion.memory_exported").one()
        assert audit.actor == "participant" and audit.patient_id == "patient-demo"
        assert set(audit.detail) == {"version"}
    assert client.post(BASE + "/forget").status_code == 200
    after = client.post(BASE + "/export").json()
    assert after["memory"]["history"] == [] and not after["memory"]["enabled"]


def test_export_role_patient_revocation_and_csrf_guards(client, database):
    for role in ["family", "clinician", "other"]:
        sign_in(client, role)
        assert client.post(BASE + "/export").status_code == 403
    sign_in(client)
    assert (
        client.post(BASE + "/export", headers={"X-CSRF-Token": "invalid"}).status_code
        == 403
    )
    assert (
        client.post("/api/patients/patient-other/companion/memory/export").status_code
        == 403
    )
    with database() as db:
        grant = (
            db.query(Grant)
            .filter_by(user_id="participant", patient_id="patient-demo")
            .one()
        )
        grant.active = False
        db.commit()
    assert client.post(BASE + "/export").status_code == 403
