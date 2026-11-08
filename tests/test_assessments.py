"""Synthetic engineering checks; these are not clinical validation results."""

import copy
import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import assessments
from app.assessment_protocol import orientation, score_session, steps, validate_response
from app.db import Grant, Patient, Receipt, Record
from app.main import app
from tests.conftest import sign_in

PATH = "/api/patients/patient-demo/assessments"


def assignment(client, **extra):
    sign_in(client, "clinician")
    body = (
        dict(
            command_id=str(uuid4()),
            protocol_version="1.0",
            timezone="Asia/Dubai",
            location="Dubai",
            acknowledge_adaptation=True,
        )
        | extra
    )
    return client.post(PATH, json=body)


def action(client, row, route, **extra):
    return client.post(
        f"{PATH}/{row['id']}/{route}",
        json=dict(command_id=str(uuid4()), expected_version=row["version"]) | extra,
    )


def start(client, **extra):
    row = assignment(client).json()
    sign_in(client)
    response = action(
        client,
        row,
        "consent",
        consent_version="assessment-research-1",
        understands_english=True,
        comfortable_reading=True,
        mode="self",
        device_class="phone",
        **extra,
    )
    assert response.status_code == 200, response.text
    return response.json()


def capture(client, monkeypatch, skip=None, difficulty="none", quality="usable"):
    row = start(client)
    clock = dt.datetime.now(dt.timezone.utc)
    monkeypatch.setattr(assessments, "now", lambda: clock.isoformat())
    private_steps = steps(orientation("Asia/Dubai", "Dubai", clock.isoformat()))
    for step in private_steps:
        response = action(client, row, "begin")
        assert response.status_code == 200, response.text
        row = response.json()
        clock += dt.timedelta(seconds=16 if step["kind"] == "learning" else 1)
        values, attempts = perfect(step)
        if step["id"] == skip:
            values, attempts = [], []
        response = action(
            client,
            row,
            "answer",
            step_id=step["id"],
            values=values,
            attempts=attempts,
            client_elapsed_ms=16000,
            difficulty=difficulty,
        )
        assert response.status_code == 200, response.text
        row = response.json()
    response = action(client, row, "transition", action="complete", quality=quality)
    assert response.status_code == 200, response.text
    return response.json()


def perfect(step):
    if step["kind"] == "stroop":
        return ["done"], [[t["color"]] for t in step["trials"]]
    if step["kind"] in {"ack", "learning"}:
        return ["done"], []
    return list(step["answer"]), []


def review_body(row, **extra):
    return (
        dict(
            outcome="reviewed_research",
            rationale="Reviewed all captured item evidence and conditions.",
            participant_note="Thank you. These research activities have been reviewed.",
            item_points={
                i["id"]: i["points"] for i in row["payload"]["score"]["items"]
            },
            checked_evidence=True,
        )
        | extra
    )


def test_complete_scoring_review_and_projections(client, monkeypatch, database):
    row = capture(client, monkeypatch)
    assert row["status"] == "awaiting_review"
    assert (
        not {"score", "steps", "responses", "reference", "consent"}
        & row["payload"].keys()
    )
    sign_in(client, "clinician")
    private = client.get(PATH).json()["sessions"][0]
    score = private["payload"]["score"]
    assert score["total"] == 30
    assert len(score["items"]) == 20
    assert [i["maximum"] for i in score["items"][:3]] == [2, 2, 2]
    assert all(r["server_elapsed_ms"] >= 0 for r in private["payload"]["responses"])
    reviewed = action(client, private, "review", **review_body(private))
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["payload"]["review"]["total"] == 30
    sign_in(client)
    participant = client.get(PATH).json()["sessions"][0]
    assert (
        "review_note" in participant["payload"]
        and "score" not in participant["payload"]
    )
    assert not any(
        r["kind"] == "assessment_session"
        for r in client.get("/api/patients/patient-demo/workspace").json()["records"]
    )
    with database() as db:
        receipts = db.query(Receipt).all()
        assert all(
            "responses" not in str(r.result) and "item_points" not in str(r.result)
            for r in receipts
        )


@pytest.mark.parametrize(
    "skip", ["reading", "learning", "recall", "stroop", "visual_2"]
)
def test_missing_evidence_not_imputed_and_not_accepted(client, monkeypatch, skip):
    capture(client, monkeypatch, skip=skip)
    sign_in(client, "clinician")
    row = client.get(PATH).json()["sessions"][0]
    if skip not in {"reading", "learning"}:
        assert row["payload"]["score"]["total"] is None
    assert action(client, row, "review", **review_body(row)).status_code == 409
    result = action(client, row, "review", **review_body(row, outcome="invalid"))
    assert result.status_code == 200, result.text
    assert result.json()["payload"]["review"]["total"] is None


@pytest.mark.parametrize("flag", ["vision", "motor", "understanding", "other"])
def test_accessibility_difficulty_requires_invalid_review(client, monkeypatch, flag):
    capture(client, monkeypatch, difficulty=flag)
    sign_in(client, "clinician")
    row = client.get(PATH).json()["sessions"][0]
    assert action(client, row, "review", **review_body(row)).status_code == 409


def test_consent_order_versions_time_limit_and_withdrawal(client, monkeypatch):
    row = assignment(client).json()
    assert (
        action(
            client,
            row,
            "consent",
            consent_version="assessment-research-1",
            understands_english=True,
            comfortable_reading=True,
            mode="self",
            device_class="tablet",
        ).status_code
        == 403
    )
    sign_in(client)
    assert action(client, row, "begin").status_code == 409
    assert (
        action(
            client,
            row,
            "consent",
            consent_version="old",
            understands_english=True,
            comfortable_reading=True,
            mode="self",
            device_class="phone",
        ).status_code
        == 422
    )
    started = action(
        client,
        row,
        "consent",
        consent_version="assessment-research-1",
        understands_english=True,
        comfortable_reading=True,
        mode="self",
        device_class="phone",
    ).json()
    assert action(client, row, "begin").status_code == 409
    assert (
        action(
            client, started, "transition", action="complete", quality="usable"
        ).status_code
        == 409
    )
    begun = action(client, started, "begin").json()
    assert (
        action(
            client,
            begun,
            "answer",
            step_id="recall",
            values=["APPLE"],
            client_elapsed_ms=1,
        ).status_code
        == 409
    )
    assert action(client, begun, "begin").status_code == 409
    clock = dt.datetime.fromisoformat(
        begun["payload"]["step_started_at"]
    ) + dt.timedelta(seconds=901)
    monkeypatch.setattr(assessments, "now", lambda: clock.isoformat())
    stopped = action(
        client, begun, "answer", step_id="reading", values=["done"], client_elapsed_ms=1
    ).json()
    assert stopped["status"] == "interrupted"
    withdrawn = action(client, stopped, "transition", action="withdraw")
    assert withdrawn.status_code == 200
    assert action(client, withdrawn.json(), "begin").status_code == 409


def test_replay_revocation_and_csrf(client, database):
    row = start(client)
    cmd = dict(command_id=str(uuid4()), expected_version=row["version"])
    route = f"{PATH}/{row['id']}/begin"
    a, b = client.post(route, json=cmd), client.post(route, json=cmd)
    assert a.status_code == b.status_code == 200
    assert a.json()["version"] == b.json()["version"]
    assert client.post(route, json=cmd | dict(expected_version=999)).status_code == 409
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post(route, json=cmd).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    with database() as db:
        grant = (
            db.query(Grant)
            .filter_by(user_id="participant", patient_id="patient-demo")
            .one()
        )
        grant.active = False
        db.commit()
    assert client.post(route, json=cmd).status_code == 403
    assert client.get(PATH).status_code == 403


@pytest.mark.parametrize("role", ["family", "other"])
def test_wrong_roles_cannot_read_or_assign(client, role):
    sign_in(client, role)
    assert client.get(PATH).status_code == 403
    assert (
        client.post(
            PATH,
            json=dict(
                command_id=str(uuid4()),
                protocol_version="1.0",
                location="Dubai",
                acknowledge_adaptation=True,
            ),
        ).status_code
        == 403
    )


def test_assignment_limits_and_real_patient_gate(client, database):
    assert assignment(client, timezone="Not/AZone").status_code == 422
    assert assignment(client, acknowledge_adaptation=False).status_code == 422
    assert assignment(client).status_code == 200
    assert assignment(client).status_code == 409
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = False
        db.commit()
    assert client.get(PATH).status_code == 403


def test_snapshot_integrity_and_cross_patient_binding(client, database):
    row = start(client)
    assert client.post(
        f"/api/patients/patient-other/assessments/{row['id']}/begin",
        json=dict(command_id=str(uuid4()), expected_version=row["version"]),
    ).status_code in {403, 404}
    with database() as db:
        record = db.get(Record, row["id"])
        p = copy.deepcopy(record.payload)
        p["steps"][1]["answer"] = ["TREE"]
        record.payload = p
        db.commit()
    assert action(client, row, "begin").status_code == 409
    assert action(client, row, "transition", action="interrupt").status_code == 200


def test_review_requires_complete_evidence_and_bounded_points(client, monkeypatch):
    capture(client, monkeypatch)
    sign_in(client, "clinician")
    row = client.get(PATH).json()["sessions"][0]
    body = review_body(row)
    points = body["item_points"]
    assert (
        action(client, row, "review", **(body | dict(item_points={}))).status_code
        == 422
    )
    for bad in [True, 0.5, -1, 3, "2"]:
        assert (
            action(
                client,
                row,
                "review",
                **(body | dict(item_points=points | dict(attention_j=bad))),
            ).status_code
            == 422
        )
    assert (
        action(
            client, row, "review", **(body | dict(checked_evidence=False))
        ).status_code
        == 422
    )
    changed = action(
        client, row, "review", **(body | dict(item_points=points | dict(attention_j=0)))
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["payload"]["review"]["total"] == 28


@pytest.mark.parametrize("errors,expected", [(0, 3), (1, 2), (2, 1), (3, 0), (5, 0)])
def test_stroop_boundaries_and_practice_exclusion(errors, expected):
    protocol = steps(
        dict(month="November", year="2026", weekday="Sunday", location="Dubai")
    )
    responses = []
    for step in protocol:
        values, attempts = perfect(step)
        if step["id"] == "stroop":
            attempts[0] = ["wrong-practice", *attempts[0]]
            attempts[3] = ["wrong"] * errors + attempts[3]
        responses.append(dict(step_id=step["id"], values=values, attempts=attempts))
    score = score_session(dict(steps=protocol, responses=responses))
    assert next(i["points"] for i in score["items"] if i["id"] == "stroop") == expected
    assert score["total"] == 27 + expected


def test_orientation_rollover_and_response_validation():
    ref = orientation("Asia/Dubai", "Dubai", "2026-12-31T22:30:00+00:00")
    assert (ref["month"], ref["year"], ref["weekday"]) == ("January", "2027", "Friday")
    protocol = steps(ref)
    with pytest.raises(ValueError):
        validate_response(protocol[1], ["JAZZ", "JAZZ"], [])
    with pytest.raises(ValueError):
        validate_response(protocol[-1], ["1"] * 8, [])
    with pytest.raises(ValueError):
        validate_response(protocol[-3], ["done"], [["blue"]])
    with pytest.raises(ValueError):
        validate_response(protocol[3], ["NaN"], [])


def test_learning_minimum_presentation_and_skip(client, monkeypatch, database):
    row = start(client)
    with database() as db:
        record = db.get(Record, row["id"])
        p = copy.deepcopy(record.payload)
        for step in p["steps"][:4]:
            values, attempts = perfect(step)
            p["responses"].append(
                dict(
                    step_id=step["id"],
                    values=values,
                    attempts=attempts,
                    difficulty="none",
                )
            )
        record.payload = p
        db.commit()
    row = action(client, row, "begin").json()
    clock = dt.datetime.fromisoformat(row["payload"]["step_started_at"])
    monkeypatch.setattr(assessments, "now", lambda: clock.isoformat())
    assert (
        action(
            client,
            row,
            "answer",
            step_id="learning",
            values=["done"],
            client_elapsed_ms=15000,
        ).status_code
        == 409
    )
    assert (
        action(
            client, row, "answer", step_id="learning", values=[], client_elapsed_ms=1
        ).status_code
        == 200
    )


def test_validation_does_not_echo_private_answers(client):
    row = start(client)
    response = action(
        client,
        row,
        "answer",
        step_id="memory_number",
        values={"private": "SENSITIVE-ANSWER"},
        client_elapsed_ms=1,
    )
    assert response.status_code == 422
    assert "SENSITIVE-ANSWER" not in response.text


def test_concurrent_assignments_are_serialized(client, database):
    with database() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("Requires PostgreSQL patient row locks")
    left = sign_in(client, "clinician")
    right = sign_in(TestClient(app), "clinician")
    barrier = threading.Barrier(2)

    def assign_one(account):
        barrier.wait(timeout=10)
        return account.post(
            PATH,
            json=dict(
                command_id=str(uuid4()),
                protocol_version="1.0",
                location="Dubai",
                acknowledge_adaptation=True,
            ),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(assign_one, account) for account in (left, right)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]
    with database() as db:
        assert (
            db.query(Record)
            .filter_by(patient_id="patient-demo", kind="assessment_session")
            .count()
            == 1
        )
