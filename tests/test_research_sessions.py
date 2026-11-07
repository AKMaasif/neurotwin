from app.db import Patient, Record
from tests.conftest import sign_in

BASE = "/api/patients/patient-demo/research/sessions"


def assignment(client):
    sign_in(client, "clinician")
    result = client.post(
        BASE,
        json={
            "command_id": "assign-session-01",
            "protocol_id": "synthetic-capture",
            "protocol_version": "1",
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def act(client, row, action, **fields):
    return client.post(
        f"{BASE}/{row['id']}/transition",
        json={
            "command_id": f"session-{action}-01",
            "expected_version": row["version"],
            "action": action,
            **fields,
        },
    )


def test_consent_completion_withdrawal_and_replay(client, database):
    row = assignment(client)
    sign_in(client)
    assert act(client, row, "complete").status_code == 409
    accepted = act(client, row, "consent", consent_version="synthetic-research-1")
    assert accepted.status_code == 200
    assert (
        act(client, row, "consent", consent_version="synthetic-research-1").json()
        == accepted.json()
    )
    active = accepted.json()
    assert act(client, active, "complete").status_code == 422
    complete = act(
        client, active, "complete", quality="usable", mode="self", device_class="phone"
    )
    assert complete.status_code == 200
    assert complete.json()["payload"]["clinical_use"] is False
    withdrawn = act(client, complete.json(), "withdraw")
    assert withdrawn.json()["status"] == "withdrawn"
    with database() as db:
        assert (
            db.query(Record).filter(Record.kind.in_(["observation", "model"])).count()
            == 0
        )


def test_roles_patient_isolation_and_proxy_consent(client):
    row = assignment(client)
    assert (
        act(client, row, "consent", consent_version="synthetic-research-1").status_code
        == 403
    )
    sign_in(client, "family")
    assert client.get(BASE).status_code == 403
    sign_in(client, "other")
    assert client.get(BASE).status_code == 403
    sign_in(client)
    assert (
        client.post(
            BASE,
            json={
                "command_id": "assign-forbidden",
                "protocol_id": "synthetic-capture",
                "protocol_version": "1",
            },
        ).status_code
        == 403
    )


def test_versions_invalid_consent_and_terminal_state(client):
    row = assignment(client)
    sign_in(client)
    assert act(client, row, "consent", consent_version="old").status_code == 409
    assert (
        act(
            client,
            row,
            "consent",
            consent_version="synthetic-research-1",
            quality="usable",
        ).status_code
        == 422
    )
    active = act(client, row, "consent", consent_version="synthetic-research-1").json()
    assert act(client, row, "interrupt").status_code == 409
    interrupted = act(client, active, "interrupt")
    assert interrupted.status_code == 200
    assert (
        act(
            client,
            interrupted.json(),
            "complete",
            quality="usable",
            mode="self",
            device_class="phone",
        ).status_code
        == 409
    )


def test_real_patient_and_unapproved_protocol_blocked(client, database):
    sign_in(client, "clinician")
    assert (
        client.post(
            BASE,
            json={
                "command_id": "unapproved-protocol",
                "protocol_id": "clinical-test",
                "protocol_version": "1",
            },
        ).status_code
        == 422
    )
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = False
        db.commit()
    assert client.get(BASE).status_code == 403


def test_receipt_bound_to_patient_and_session(client):
    row = assignment(client)
    sign_in(client)
    active = act(client, row, "consent", consent_version="synthetic-research-1").json()
    result = act(client, active, "cancel")
    assert result.status_code == 200
    assert (
        act(client, active, "cancel", consent_version="unexpected").status_code == 409
    )
    listed = client.get(BASE).json()
    assert listed["sessions"][0]["status"] == "cancelled"
    assert listed["protocol"]["consent_text"]


def test_stale_protocol_requires_reassignment(client, database):
    row = assignment(client)
    with database() as db:
        stored = db.get(Record, row["id"])
        stored.payload = stored.payload | {"protocol": {"version": "obsolete"}}
        db.commit()
    sign_in(client)
    assert (
        act(client, row, "consent", consent_version="synthetic-research-1").status_code
        == 409
    )
    assert act(client, row, "cancel").status_code == 200
