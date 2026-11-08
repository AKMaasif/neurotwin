import pytest

from app.arabic import command, localize
from app.db import Record
from tests.conftest import sign_in


@pytest.mark.parametrize(
    "text,expected",
    [
        ("افتح الإعدادات", "open settings"),
        ("اِفْتَح الإعدادات", "open settings"),
        ("افتح خطتي", "open plan"),
        ("افتح الرسائل", "open messages"),
        ("افتح الدعم", "open support"),
        ("افتح الفحص", "open my check"),
        ("كبر الخط", "larger text"),
        ("توقف", "stop"),
        ("إلغاء", "cancel"),
        ("اقرأ خطتي", "read my plan"),
        ("انتهيت", "i finished"),
        ("افعل هذا لاحقًا", "do this later"),
    ],
)
def test_arabic_command_matrix(text, expected):
    assert command(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "لا تفتح الإعدادات",
        "لا تكبر الخط",
        "لن افتح خطتي",
        "افتح الرسائل وافتح الدعم",
        "امسح جميع المرضى",
        "غيّر الدواء",
    ],
)
def test_negated_ambiguous_or_unsupported_commands_do_not_execute(text):
    assert command(text) == "do not perform an action"


def test_arabic_proposals_confirmations_and_no_silent_care_translation(
    client, database
):
    sign_in(client)
    path = "/api/patients/patient-demo/companion"
    r = client.post(path, json={"text": "افتح الإعدادات", "locale": "ar"})
    assert r.status_code == 200 and r.json()["screen"] == "settings"
    assert "الإعدادات" in r.json()["explanation"]
    with database() as db:
        before = [(r.id, r.version) for r in db.query(Record).all()]
    r = client.post(path, json={"text": "كبر الخط", "locale": "ar"}).json()
    assert r["requires_confirmation"] and r["action_status"] == "proposal_only"
    with database() as db:
        assert before == [(r.id, r.version) for r in db.query(Record).all()]
    r = client.post(path, json={"text": "لا تفتح الإعدادات", "locale": "ar"}).json()
    assert r["intent"] == "clarify"
    r = client.post(path, json={"text": "اقرأ خطتي", "locale": "ar"}).json()
    assert r["original_language_content"] is True
    assert (
        client.post(path, json={"text": "افتح الدعم", "locale": "xx"}).status_code
        == 422
    )


def test_arabic_emergency_precedes_negation_and_navigation(client):
    sign_in(client)
    r = client.post(
        "/api/patients/patient-demo/companion",
        json={"text": "افتح الإعدادات لا أستطيع التنفس", "locale": "ar"},
    ).json()
    assert r["intent"] == "clinical_review" and r["action_status"] == "not_executed"
    assert "لم يتم الاتصال" in r["explanation"]


def test_retired_routes_and_assets_absent(client):
    sign_in(client)
    assert (
        client.get("/api/patients/patient-demo/iot-simulation/sessions").status_code
        == 404
    )
    assert client.get("/dashboard/iot-simulation.js").status_code == 404
    from app.main import app

    assert not any("iot-simulation" in path for path in app.openapi()["paths"])
    assert (
        localize({"intent": "stop", "explanation": "Stopped"}, "ar")["locale"] == "ar"
    )
