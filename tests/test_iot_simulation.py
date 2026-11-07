import datetime as dt

from app.db import Grant, Patient, Record
from tests.conftest import sign_in

BASE = "/api/patients/patient-demo/iot-simulation"


def permit(client):
    sign_in(client)
    result = client.post(
        BASE + "/permission",
        json={
            "command_id": "simulation-permission",
            "expected_version": 0,
            "enabled": True,
            "consent_version": "iot-simulation-1",
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def inject(client, state, kind, **updates):
    return client.post(
        BASE + "/events",
        json={
            "command_id": "simulate-" + kind,
            "expected_version": state["version"],
            "sequence": state["payload"]["sequence"] + 1,
            "occurred_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "kind": kind,
        }
        | updates,
    )


def test_permission_required_and_no_proxy_consent(client):
    sign_in(client, "clinician")
    state = {"version": 1, "payload": {"sequence": 0}}
    assert inject(client, state, "connected").status_code == 409
    assert (
        client.post(
            BASE + "/permission",
            json={
                "command_id": "proxy-consent-01",
                "expected_version": 0,
                "enabled": True,
                "consent_version": "iot-simulation-1",
            },
        ).status_code
        == 403
    )
    sign_in(client)
    assert (
        client.post(
            BASE + "/permission",
            json={
                "command_id": "bad-consent-01",
                "expected_version": 0,
                "enabled": True,
                "consent_version": "old",
            },
        ).status_code
        == 409
    )


def test_disconnect_missing_fault_and_recovery(client, database):
    state = permit(client)
    sign_in(client, "clinician")
    assert inject(client, state, "reading", value=3).status_code == 409
    state = inject(client, state, "connected").json()["state"]
    result = inject(client, state, "reading", value=3)
    assert result.status_code == 200
    assert result.json()["event"]["payload"]["source_type"] == "simulated_device"
    assert result.json()["event"]["payload"]["unit"] == "count"
    state = result.json()["state"]
    state = inject(client, state, "disconnected").json()["state"]
    assert (
        inject(
            client, state, "reading", value=3, command_id="reading-after-disconnect"
        ).status_code
        == 409
    )
    state = inject(client, state, "missing_reading").json()["state"]
    assert state["payload"]["connection"] == "disconnected"
    state = inject(client, state, "fault").json()["state"]
    assert state["payload"]["connection"] == "faulted"
    state = inject(client, state, "connected", command_id="recovery-connect").json()[
        "state"
    ]
    assert (
        inject(
            client, state, "reading", value=2, command_id="reading-after-recovery"
        ).status_code
        == 200
    )
    with database() as db:
        assert (
            db.query(Record)
            .filter(Record.kind.in_(["observation", "model", "case"]))
            .count()
            == 0
        )


def test_sequence_timestamp_value_validation_and_retry(client):
    state = permit(client)
    sign_in(client, "clinician")
    body = {
        "command_id": "ordered-connect",
        "expected_version": state["version"],
        "sequence": 3,
        "occurred_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kind": "connected",
    }
    result = client.post(BASE + "/events", json=body)
    assert result.status_code == 200
    assert result.json()["event"]["payload"]["sequence_gap"] == 2
    assert client.post(BASE + "/events", json=body).json() == result.json()
    assert client.post(BASE + "/events", json=body | {"sequence": 4}).status_code == 409
    state = result.json()["state"]
    assert inject(client, state, "reading", sequence=3, value=1).status_code == 409
    assert (
        inject(
            client, state, "reading", occurred_at="2020-01-01T00:00:00Z", value=1
        ).status_code
        == 409
    )
    assert (
        inject(
            client, state, "reading", occurred_at="2099-01-01T00:00:00Z", value=1
        ).status_code
        == 422
    )
    assert (
        inject(
            client, state, "reading", occurred_at="2026-01-01T00:00:00", value=1
        ).status_code
        == 422
    )
    for value in [-1, 1.5, True, "3"]:
        assert inject(client, state, "reading", value=value).status_code == 422
    assert inject(client, state, "reading").status_code == 422
    assert inject(client, state, "missing_reading", value=0).status_code == 422


def test_withdrawal_blocks_injection_and_stale_permission_changes(client):
    state = permit(client)
    withdrawn = client.post(
        BASE + "/permission",
        json={
            "command_id": "withdraw-simulation",
            "expected_version": state["version"],
            "enabled": False,
        },
    )
    assert withdrawn.status_code == 200
    sign_in(client, "clinician")
    assert inject(client, withdrawn.json(), "connected").status_code == 409
    sign_in(client)
    replayed = client.post(
        BASE + "/permission",
        json={
            "command_id": "simulation-permission",
            "expected_version": 0,
            "enabled": True,
            "consent_version": "iot-simulation-1",
        },
    )
    assert replayed.status_code == 200  # Original receipt, not a new consent action.
    assert client.get(BASE).json()["state"]["status"] == "withdrawn"
    assert (
        client.post(
            BASE + "/permission",
            json={
                "command_id": "old-version-enable",
                "expected_version": 1,
                "enabled": True,
                "consent_version": "iot-simulation-1",
            },
        ).status_code
        == 409
    )


def test_review_signal_requires_explicit_clinician_review(client):
    state = permit(client)
    assert inject(client, state, "review_signal").status_code == 403
    sign_in(client, "clinician")
    result = inject(client, state, "review_signal").json()
    event = result["event"]
    assert event["status"] == "awaiting_review"
    review_path = BASE + "/events/" + event["id"] + "/review"
    command = {
        "command_id": "review-simulation",
        "expected_version": event["version"],
        "decision": "acknowledged",
    }
    sign_in(client)
    assert client.post(review_path, json=command).status_code == 403
    sign_in(client, "clinician")
    reviewed = client.post(review_path, json=command)
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["payload"]["review"]["actor"] == "clinician"
    assert client.post(review_path, json=command).json() == reviewed.json()


def test_scope_family_patient_and_real_data_boundaries(client, database):
    permit(client)
    sign_in(client, "family")
    assert client.get(BASE).status_code == 403
    sign_in(client, "other")
    assert client.get(BASE).status_code == 403
    sign_in(client)
    assert client.get(BASE.replace("patient-demo", "patient-other")).status_code == 403
    assert client.get(BASE).json()["state"]["status"] == "enabled"
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = False
        db.commit()
    assert client.get(BASE).status_code == 403


def test_revoked_grant_and_stale_versions(client, database):
    state = permit(client)
    sign_in(client, "clinician")
    assert inject(client, state, "connected", expected_version=999).status_code == 409
    with database() as db:
        db.query(Grant).filter_by(
            user_id="clinician", patient_id="patient-demo"
        ).one().active = False
        db.commit()
    assert inject(client, state, "connected").status_code == 403


def test_participant_access_revocation_stops_injection(client, database):
    state = permit(client)
    sign_in(client, "clinician")
    with database() as db:
        db.query(Grant).filter_by(
            user_id="participant", patient_id="patient-demo"
        ).one().active = False
        db.commit()
    assert inject(client, state, "connected").status_code == 409


def test_event_history_is_bounded_and_pageable(client, database):
    permit(client)
    with database() as db:
        for sequence in range(53):
            db.add(
                Record(
                    patient_id="patient-demo",
                    kind="iot_sim_event",
                    status="recorded",
                    payload={"sequence": sequence},
                )
            )
        db.commit()
    first = client.get(BASE).json()
    second = client.get(BASE + "?offset=50").json()
    assert first["total"] == 53
    assert len(first["events"]) == 50
    assert len(second["events"]) == 3
    assert not (
        {r["id"] for r in first["events"]} & {r["id"] for r in second["events"]}
    )
    assert client.get(BASE + "?offset=-1").status_code == 422


def test_client_cannot_label_events_as_physical_telemetry(client):
    state = permit(client)
    sign_in(client, "clinician")
    assert inject(client, state, "connected", simulated=False).status_code == 422
    connected = inject(client, state, "connected").json()
    assert connected["event"]["payload"]["simulated"] is True
    assert connected["event"]["payload"]["clinical_use"] is False
