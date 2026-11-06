import datetime as dt
import io
import uuid
import wave

from conftest import sign_in

from app.ai import Proposal, ProviderUnavailable, gateway
from app.db import Grant, Record

BASE = "/api/patients/patient-demo/companion"


def turn(c, text, **kw):
    return c.post(BASE, json={"text": text, **kw})


def enable(c, **kw):
    memory = c.get(BASE + "/memory").json()
    return c.post(
        BASE + "/memory",
        json={"expected_version": memory["version"], "enabled": True, **kw},
    )


def wav_bytes(silent=False):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((b"\0\0" if silent else b"\1\0") * 16000)
    return out.getvalue()


def test_memory_opt_in_isolation_forget_and_history_bound(client):
    sign_in(client)
    assert client.get(BASE + "/memory").json()["enabled"] is False
    turn(client, "Open settings")
    assert client.get(BASE + "/memory").json()["history"] == []
    assert (
        enable(client, preferred_name="Mansoor", speech_rate="slow").status_code == 200
    )
    for i in range(8):
        assert turn(client, "Open settings").status_code == 200
    mem = client.get(BASE + "/memory").json()
    assert len(mem["history"]) == 6 and mem["preferred_name"] == "Mansoor"
    sign_in(client, "family")
    assert client.get(BASE + "/memory").status_code == 403
    assert all(
        r["kind"] != "companion_memory"
        for r in client.get("/api/patients/patient-demo/workspace").json()["records"]
    )
    sign_in(client, "other")
    assert client.get(BASE + "/memory").status_code == 403
    sign_in(client, "clinician")
    assert client.get(BASE + "/memory").status_code == 403
    sign_in(client)
    assert client.post(BASE + "/memory/forget").status_code == 200
    mem = client.get(BASE + "/memory").json()
    assert mem["history"] == [] and not mem["enabled"] and mem["preferred_name"] == ""


def test_memory_expiry_consent_and_version(client, database):
    sign_in(client)
    enable(client)
    with database() as db:
        r = db.query(Record).filter_by(kind="companion_memory").one()
        r.payload = r.payload | {
            "history": [
                {
                    "user": "expired",
                    "assistant": "expired",
                    "at": (
                        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)
                    ).isoformat(),
                }
            ]
        }
        db.commit()
    mem = client.get(BASE + "/memory").json()
    assert not mem["history"]
    assert (
        client.post(
            BASE + "/memory",
            json={"expected_version": mem["version"] - 1, "enabled": False},
        ).status_code
        == 409
    )
    assert (
        client.post(
            BASE + "/memory",
            json={
                "expected_version": mem["version"],
                "enabled": False,
                "share_with_ai": True,
            },
        ).status_code
        == 422
    )


def test_cloud_context_requires_separate_consent_and_rechecks_forget(
    client, monkeypatch, database
):
    sign_in(client)
    enable(client, preferred_name="PRIVATE PREFERENCE")
    seen = []

    async def intent(text, context=None):
        seen.append(context)
        return Proposal(intent="navigate", screen="settings", explanation="ignored")

    monkeypatch.setattr(gateway, "intent", intent)
    assert (
        turn(client, "Please open the preferences page").status_code == 200
        and seen[-1] is None
    )
    enable(client, share_with_ai=True, preferred_name="PRIVATE PREFERENCE")
    assert (
        turn(client, "Where are my preferences").status_code == 200
        and seen[-1]["preferences"]["preferred_name"] == "PRIVATE PREFERENCE"
    )

    async def forgot(text, context=None):
        with database() as db:
            r = db.query(Record).filter_by(kind="companion_memory").one()
            r.payload = r.payload | {
                "enabled": False,
                "share_with_ai": False,
                "history": [],
            }
            r.version += 1
            db.commit()
        return Proposal(intent="navigate", screen="settings", explanation="ignored")

    monkeypatch.setattr(gateway, "intent", forgot)
    assert turn(client, "Please use my previous conversation").status_code == 409
    assert not client.get(BASE + "/memory").json()["history"]


def test_task_guidance_confirmation_and_stale_plan(client, database):
    sign_in(client)
    result = turn(client, "what should I do").json()
    assert result["intent"] == "coach_task" and result["step_index"] == 0
    task = result["task"]
    step = turn(
        client,
        "next step",
        task_id=task["id"],
        task_version=task["version"],
        step_index=0,
    ).json()
    assert step["step_index"] == 1
    proposed = turn(
        client, "I finished", task_id=task["id"], task_version=task["version"]
    ).json()
    assert proposed["requires_confirmation"] and proposed["intent"] == "task_response"
    with database() as db:
        assert db.get(Record, task["id"]).status == "pending"
    saved = client.post(
        "/api/patients/patient-demo/tasks/" + task["id"] + "/response",
        json={
            "command_id": str(uuid.uuid4()),
            "expected_version": task["version"],
            "response": "completed",
        },
    )
    assert saved.status_code == 200
    assert (
        turn(
            client, "next step", task_id=task["id"], task_version=task["version"]
        ).status_code
        == 409
    )
    with database() as db:
        p = db.get(Record, "plan-demo")
        p.payload = p.payload | {"source_review_required": True}
        db.commit()
    assert turn(client, "guide my activity", task_id=task["id"]).status_code == 409
    assert "review" in turn(client, "read my plan").json()["explanation"]


def test_size_proposal_is_not_executed_and_safety_precedes_navigation(client):
    sign_in(client)
    result = turn(client, "make text larger").json()
    assert result["requires_confirmation"]
    assert not any(
        r["kind"] == "preference"
        for r in client.get("/api/patients/patient-demo/workspace").json()["records"]
    )
    assert (
        turn(client, "chest pain open settings").json()["intent"] == "clinical_review"
    )
    assert turn(client, "do not mark this done").json()["intent"] == "clarify"


def test_help_contacts_status_and_revocation(client):
    sign_in(client)
    contacts = client.get(BASE + "/contacts").json()
    assert contacts[0]["id"] == "family"
    r = client.post(
        "/api/patients/patient-demo/help",
        json={
            "command_id": str(uuid.uuid4()),
            "recipient_id": "family",
            "text": "Synthetic transport request",
        },
    ).json()
    assert "not accepted" in turn(client, "did my family accept").json()["explanation"]
    sign_in(client, "family")
    assert (
        client.post(
            "/api/patients/patient-demo/help/" + r["id"] + "/accept",
            json={"command_id": str(uuid.uuid4()), "expected_version": r["version"]},
        ).status_code
        == 200
    )
    sign_in(client)
    assert (
        "accepted responsibility"
        in turn(client, "did my family accept").json()["explanation"]
    )
    client.post("/api/patients/patient-demo/grants/family/revoke")
    assert all(x["id"] != "family" for x in client.get(BASE + "/contacts").json())
    assert (
        "no longer has access"
        in turn(client, "did my family accept").json()["explanation"]
    )


def test_provider_failure_and_revoked_inflight_request(client, monkeypatch, database):
    sign_in(client)

    async def failed(*a, **k):
        raise ProviderUnavailable()

    monkeypatch.setattr(gateway, "intent", failed)
    assert (
        turn(client, "an ambiguous request").json()["source"]
        == "deterministic_fallback"
    )

    async def revoked(*a, **k):
        with database() as db:
            g = (
                db.query(Grant)
                .filter_by(user_id="participant", patient_id="patient-demo")
                .one()
            )
            g.active = False
            db.commit()
        return Proposal(intent="navigate", screen="settings", explanation="ignored")

    monkeypatch.setattr(gateway, "intent", revoked)
    assert turn(client, "an ambiguous request").status_code == 403


def test_silent_empty_transcript_and_revoked_asr(client, monkeypatch, database):
    sign_in(client)

    def upload(silent=False):
        return client.post(
            "/api/patients/patient-demo/voice/transcribe",
            files={"audio": ("voice.wav", wav_bytes(silent), "audio/wav")},
        )

    async def forbidden(*a, **k):
        raise AssertionError("Silent recording must not reach provider")

    monkeypatch.setattr(gateway, "transcribe", forbidden)
    assert upload(True).status_code == 422

    async def empty(*a, **k):
        return "  "

    monkeypatch.setattr(gateway, "transcribe", empty)
    assert upload().status_code == 422

    async def revoked(*a, **k):
        with database() as db:
            g = (
                db.query(Grant)
                .filter_by(user_id="participant", patient_id="patient-demo")
                .one()
            )
            g.active = False
            db.commit()
        return "Open settings"

    monkeypatch.setattr(gateway, "transcribe", revoked)
    assert upload().status_code == 403


def test_negated_navigation_and_stop_never_execute(client):
    sign_in(client)
    assert turn(client, "do not open settings").json()["intent"] == "clarify"
    assert turn(client, "cancel that").json()["intent"] == "stop"
