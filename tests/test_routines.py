import datetime as dt
import uuid

import pytest
from conftest import sign_in

from app.db import Record, Reminder, RoutineOccurrence
from app.routines import outside_quiet, resolve_wall, tick

BASE = "/api/patients/patient-demo/routines"
AT = dt.datetime(2026, 11, 6, 8, tzinfo=dt.timezone.utc)


@pytest.fixture
def instant(monkeypatch):
    state = {"at": AT}
    monkeypatch.setattr("app.routines.utcnow", lambda: state["at"])
    return state


def create(c, template="task-01", **kw):
    return c.post(
        BASE,
        json={
            "template_id": template,
            "template_version": 1,
            "timezone": "Asia/Dubai",
            "local_time": "12:00",
            "weekdays": list(range(7)),
            "start_date": "2026-11-06",
            "end_date": "2026-11-10",
            **kw,
        },
    )


def listed(c):
    return c.get(BASE).json()


def consent(c, r, **kw):
    return c.post(
        BASE + "/" + r["id"] + "/consent",
        json={
            "expected_version": r["version"],
            "active": True,
            "family_followup": False,
            **kw,
        },
    )


def run(database, instant, minutes=0):
    instant["at"] = AT + dt.timedelta(minutes=minutes)
    with database() as db:
        tick(db, instant["at"])
        db.commit()


def action(c, o, response="completed", **kw):
    return c.post(
        BASE + "/occurrences/" + o["id"] + "/response",
        json={
            "command_id": str(uuid.uuid4()),
            "task_version": o["task"]["version"],
            "routine_version": o["routine_version"],
            "response": response,
            **kw,
        },
    )


def test_wall_time_fold_gap_and_quiet_hours():
    due, resolution = resolve_wall(dt.date(2026, 3, 8), "02:30", "America/New_York")
    assert due.hour == 7 and due.minute == 0 and resolution == "shifted_to_valid_minute"
    due, resolution = resolve_wall(dt.date(2026, 11, 1), "01:30", "America/New_York")
    assert due.hour == 5 and resolution == "earlier_fold"
    q = outside_quiet(
        dt.datetime(2026, 11, 6, 18, tzinfo=dt.timezone.utc),
        {"timezone": "Asia/Dubai", "quiet_start": "21:00", "quiet_end": "07:00"},
    )
    assert q == dt.datetime(2026, 11, 7, 3, tzinfo=dt.timezone.utc)


def test_clinician_proposal_requires_participant_consent(client, database, instant):
    sign_in(client, "clinician")
    r = create(client)
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["status"] == "awaiting_consent"
    run(database, instant)
    assert not listed(client)["occurrences"]
    assert consent(client, r).status_code == 403
    sign_in(client)
    assert consent(client, r).status_code == 200
    run(database, instant)
    assert len(listed(client)["occurrences"]) == 1


def test_occurrence_and_reminder_dedup_and_unknown_not_missed(
    client, database, instant
):
    sign_in(client)
    r = create(client).json()
    run(database, instant)
    run(database, instant)
    data = listed(client)
    assert len(data["occurrences"]) == 1 and len(data["reminders"]) == 1
    assert data["occurrences"][0]["task"]["status"] == "pending"
    n = data["reminders"][0]
    assert (
        client.post(
            BASE + "/reminders/" + n["id"] + "/acknowledge",
            json={"expected_version": n["version"], "action": "acknowledge"},
        ).json()["activity_completed"]
        is False
    )
    assert listed(client)["occurrences"][0]["task"]["status"] == "pending"
    run(database, instant, minutes=2 * 24 * 60)
    with database() as db:
        first = (
            db.query(RoutineOccurrence)
            .filter_by(routine_id=r["id"], local_date="2026-11-06")
            .one()
        )
        assert first.status == "expired"
        assert db.get(Record, first.task_id).status == "unconfirmed"
    report = client.get("/api/patients/patient-demo/report").json()
    assert report["counts"]["unconfirmed"] == 1 and "missed" not in report["counts"]


def test_snooze_followup_acknowledgement_and_acceptance(client, database, instant):
    sign_in(client)
    r = create(client).json()
    r = consent(
        client, r, family_followup=True, recipient_id="family", grace_minutes=15
    ).json()
    run(database, instant)
    o = listed(client)["occurrences"][0]
    assert action(client, o, "snooze").status_code == 200
    run(database, instant, 14)
    assert listed(client)["reminders"] == []
    run(database, instant, 15)
    assert len(listed(client)["reminders"]) == 1
    run(database, instant, 29)
    with database() as db:
        assert db.query(Record).filter_by(kind="help").count() == 0
    run(database, instant, 30)
    run(database, instant, 31)
    with database() as db:
        assert db.query(Record).filter_by(kind="help").count() == 1
    sign_in(client, "family")
    data = listed(client)
    assert len(data["reminders"]) == 1
    o = data["occurrences"][0]
    assert o["help_status"] == "requested"
    n = data["reminders"][0]
    assert (
        client.post(
            BASE + "/reminders/" + n["id"] + "/acknowledge",
            json={"expected_version": n["version"], "action": "acknowledge"},
        ).status_code
        == 200
    )
    assert listed(client)["occurrences"][0]["help_status"] == "requested"
    h = client.get("/api/patients/patient-demo/workspace").json()["records"]
    h = next(x for x in h if x["id"] == o["help_id"])
    assert (
        client.post(
            "/api/patients/patient-demo/help/" + h["id"] + "/accept",
            json={"command_id": str(uuid.uuid4()), "expected_version": h["version"]},
        ).status_code
        == 200
    )
    assert listed(client)["occurrences"][0]["help_status"] == "accepted"
    sign_in(client)
    o = listed(client)["occurrences"][0]
    assert action(client, o).status_code == 200
    assert listed(client)["occurrences"][0]["help_status"] == "resolved"


def test_grant_revocation_blocks_notifications_and_new_followup(
    client, database, instant
):
    sign_in(client)
    r = create(client).json()
    consent(client, r, family_followup=True, recipient_id="family", grace_minutes=15)
    run(database, instant)
    client.post("/api/patients/patient-demo/grants/family/revoke")
    run(database, instant, 20)
    with database() as db:
        assert db.query(Record).filter_by(kind="help").count() == 0
    sign_in(client, "family")
    assert client.get(BASE).status_code == 403


def test_manual_help_without_auto_consent(client, database, instant):
    sign_in(client)
    create(client)
    run(database, instant)
    o = listed(client)["occurrences"][0]
    assert action(client, o, "help", recipient_id="family").status_code == 200
    sign_in(client, "family")
    data = listed(client)
    assert (
        len(data["reminders"]) == 1
        and data["occurrences"][0]["help_status"] == "requested"
    )


def test_pause_resume_and_source_correction_cancel_old_reminders(
    client, database, instant
):
    sign_in(client)
    r = create(client).json()
    run(database, instant)
    o = listed(client)["occurrences"][0]
    n = listed(client)["reminders"][0]
    paused = consent(client, r, active=False).json()
    assert listed(client)["reminders"] == []
    assert action(client, o).status_code == 409
    assert (
        client.post(
            BASE + "/reminders/" + n["id"] + "/device",
            json={
                "expected_version": n["version"],
                "device_id": "synthetic-device",
                "state": "claim",
            },
        ).status_code
        == 409
    )
    consent(client, paused)
    run(database, instant)
    assert len(listed(client)["occurrences"]) == 1
    with database() as db:
        p = db.get(Record, "plan-demo")
        p.payload = p.payload | {"source_review_required": True}
        p.version += 1
        db.commit()
    run(database, instant)
    assert (
        listed(client)["routines"][0]["status"] == "review_required"
        and not listed(client)["reminders"]
    )


def test_response_idempotency_stale_offline_conflict_and_permissions(
    client, database, instant
):
    sign_in(client)
    create(client)
    run(database, instant)
    o = listed(client)["occurrences"][0]
    body = {
        "command_id": str(uuid.uuid4()),
        "task_version": o["task"]["version"],
        "routine_version": o["routine_version"],
        "response": "completed",
    }
    url = BASE + "/occurrences/" + o["id"] + "/response"
    first = client.post(url, json=body)
    second = client.post(url, json=body)
    assert first.status_code == 200 and first.json() == second.json()
    assert client.post(url, json=body | {"response": "snooze"}).status_code == 409
    assert action(client, o).status_code == 409
    sign_in(client, "family")
    assert create(client).status_code == 403
    assert action(client, o).status_code == 403
    sign_in(client, "other")
    assert client.get(BASE).status_code == 403


def test_device_claims_deduplicate_and_never_claim_delivery(client, database, instant):
    sign_in(client)
    create(client)
    run(database, instant)
    n = listed(client)["reminders"][0]
    url = BASE + "/reminders/" + n["id"] + "/device"
    body = {
        "expected_version": n["version"],
        "device_id": "synthetic-device",
        "state": "claim",
    }
    assert client.post(url, json=body).json()["claimed"] is True
    assert client.post(url, json=body).json()["claimed"] is False
    assert (
        client.post(url, json=body | {"state": "requested"}).json()[
            "delivery_confirmed"
        ]
        is False
    )
    assert listed(client)["reminders"][0]["device_states"] == ["requested"]
    sign_in(client, "family")
    assert client.post(url, json=body).status_code == 404


def test_quiet_hours_and_validation(client, database, instant):
    sign_in(client)
    assert create(client, timezone="Not/AZone").status_code == 422
    assert create(client, weekdays=[7]).status_code == 422
    assert create(client, end_date="2025-01-01").status_code == 422
    r = create(client).json()
    consent(client, r, quiet_start="11:00", quiet_end="13:00")
    run(database, instant)
    assert not listed(client)["reminders"]
    run(database, instant, 60)
    assert len(listed(client)["reminders"]) == 1
    assert create(client).status_code == 409


def test_late_response_is_rejected_even_if_worker_was_unavailable(
    client, database, instant
):
    sign_in(client)
    create(client)
    run(database, instant)
    occurrence = listed(client)["occurrences"][0]
    instant["at"] = AT + dt.timedelta(hours=25)
    assert action(client, occurrence).status_code == 409


def test_multiple_scheduler_runs_share_one_occurrence(client, database, instant):
    from concurrent.futures import ThreadPoolExecutor

    sign_in(client)
    create(client)

    def scheduled_run():
        with database() as db:
            tick(db, AT)
            db.commit()

    with database() as db:
        postgres = db.bind.dialect.name == "postgresql"
    if postgres:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: scheduled_run(), range(4)))
    else:
        scheduled_run()
        scheduled_run()
    with database() as db:
        assert db.query(RoutineOccurrence).count() == 1
        assert db.query(Reminder).count() == 1


def test_changed_help_recipient_cancels_previous_request(client, database, instant):
    from app.db import Grant, User

    sign_in(client)
    create(client)
    run(database, instant)
    occurrence = listed(client)["occurrences"][0]
    assert action(client, occurrence, "help", recipient_id="family").status_code == 200
    with database() as db:
        db.add(
            User(
                id="family-second",
                name="Second fictional relative",
                role="family",
                password_hash=db.get(User, "family").password_hash,
            )
        )
        db.flush()
        db.add(
            Grant(
                user_id="family-second",
                patient_id="patient-demo",
                scopes=["summary", "help"],
                active=True,
            )
        )
        db.commit()
    occurrence = listed(client)["occurrences"][0]
    assert (
        action(client, occurrence, "help", recipient_id="family-second").status_code
        == 200
    )
    with database() as db:
        old = db.query(Record).filter_by(kind="help").all()
        assert (
            next(r for r in old if r.payload["recipient_id"] == "family").status
            == "cancelled"
        )
        assert (
            next(r for r in old if r.payload["recipient_id"] == "family-second").status
            == "requested"
        )
