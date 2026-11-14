"""Emergency access: configured numbers, a trusted person only the user can see, and copy that never claims a call connected or help is
coming. Nothing here places a call or contacts anyone (there is no code path that could), and tests use no telephony of any kind."""
import re
from pathlib import Path

import pytest

from test_careplan import sign_in

I18N = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n.ts").read_text(encoding="utf-8")


def test_defaults_and_owner_override(client, monkeypatch):
    h = sign_in(client, "demo-fatima")
    c = client.get("/api/emergency/config").json()
    assert c["region"] == "AE" and [(n["id"], n["number"]) for n in c["numbers"]] == [("ambulance", "998"), ("police", "999")]
    assert c["verified"] is False and c["trusted"] is None              # the owner has not verified: the screen says so
    monkeypatch.setenv("NEUROTWIN_EMERGENCY_NUMBERS", "ambulance:911,fire:912")
    monkeypatch.setenv("NEUROTWIN_EMERGENCY_REGION", "us")
    monkeypatch.setenv("NEUROTWIN_EMERGENCY_VERIFIED", "1")
    c = client.get("/api/emergency/config").json()
    assert [(n["id"], n["number"]) for n in c["numbers"]] == [("ambulance", "911"), ("fire", "912")] and c["region"] == "US" and c["verified"]


@pytest.mark.parametrize("raw", ["ambulance:abc", "police:99999999", "x:999", "ambulance:999;rm", ""])
def test_bad_owner_numbers_fall_back_to_defaults(client, monkeypatch, raw):
    sign_in(client, "demo-fatima")
    monkeypatch.setenv("NEUROTWIN_EMERGENCY_NUMBERS", raw)
    assert [n["number"] for n in client.get("/api/emergency/config").json()["numbers"]] == ["998", "999"]


def test_trusted_person_is_private_and_validated(client):
    h = sign_in(client, "demo-fatima")
    assert client.put("/api/emergency/trusted", json={"name": "Mariam", "phone": "javascript:alert(1)"}, headers=h).status_code == 422
    assert client.put("/api/emergency/trusted", json={"name": "Mariam", "phone": "12"}, headers=h).status_code == 422
    assert client.put("/api/emergency/trusted", json={"name": "  ", "phone": "+971 50 123 4567"}, headers=h).status_code == 422
    assert client.put("/api/emergency/trusted", json={"name": "Mariam", "phone": "+971 50 123 4567"}, headers=h).status_code == 200
    assert client.get("/api/emergency/config").json()["trusted"] == {"name": "Mariam", "phone": "+971 50 123 4567"}
    hy = sign_in(client, "demo-yousef")
    assert client.get("/api/emergency/config").json()["trusted"] is None
    for who in ("demo-dr-layla", "demo-mariam"):
        hh = sign_in(client, who)
        assert client.get("/api/emergency/config").json()["trusted"] is None
        assert client.put("/api/emergency/trusted", json={"name": "x", "phone": "123456"}, headers=hh).status_code == 404
        assert client.delete("/api/emergency/trusted", headers=hh).status_code == 404
    h = sign_in(client, "demo-fatima")
    assert client.delete("/api/emergency/trusted", headers=h).status_code == 200
    assert client.get("/api/emergency/config").json()["trusted"] is None


def test_the_number_is_not_written_to_the_audit_log(client, app):
    h = sign_in(client, "demo-fatima")
    client.put("/api/emergency/trusted", json={"name": "Mariam", "phone": "+971501234567"}, headers=h)
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        assert "971" not in str([(a.action, a.target) for a in db.query(AuditEvent).all()])


def test_config_needs_sign_in(client):
    assert client.get("/api/emergency/config").status_code in (401, 403)


def test_the_module_has_no_way_to_call_or_message():
    src = (Path(__file__).resolve().parents[1] / "app" / "emergency.py").read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", src)           # ignore the docstring that explains what it never does
    for forbidden in ("requests", "httpx", "smtplib", "twilio", "urllib", "socket", "subprocess", "notify"):
        assert forbidden not in code


def urgent_strings() -> dict[str, str]:
    return {k: v for k, v in re.findall(r'^\s*((?:urgent|em)[A-Za-z0-9_]*):\s*"((?:[^"\\]|\\.)*)"', I18N, re.M)}


def test_copy_never_claims_a_call_connected_or_help_is_coming():
    strings = urgent_strings()
    assert len(strings) > 20                                              # both languages found
    bad = ["on the way", "on its way", "is coming", "will come", "has been called", "we have called", "we called", "connected to", "contacted",
           "notified", "alerted", "dispatched", "help is", "someone will", "we will send",
           "في الطريق", "سيأتي", "تم الاتصال", "جاري الاتصال", "تم إبلاغ", "تم تنبيه", "سيصل", "ستصل المساعدة", "سنرسل"]
    for key, text in strings.items():
        low = text.lower()
        for phrase in bad:
            assert phrase not in low, f"{key}: {phrase}"


def test_copy_says_what_the_screen_cannot_do_in_both_languages():
    strings = urgent_strings()
    for lang_key in ("emLimits",):
        assert strings[lang_key]
    en = [v for k, v in re.findall(r'^\s*(emLimits):\s*"((?:[^"\\]|\\.)*)"', I18N, re.M)]
    assert len(en) == 2 and "cannot place the call" in en[0] and "لا يستطيع" in en[1]
