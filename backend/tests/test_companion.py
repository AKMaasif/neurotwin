"""Voice companion backend: the flag, what is offered to whom, server speech rules. No live provider is ever called."""
import base64
import json

import httpx
import pytest

from app import companion as COMP
from app import llm


def login(client, name="fatima"):
    r = client.post("/api/auth/demo-enter", json={"username": name})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf"]}


def consent(client, h, scope, granted=True):
    r = client.post("/api/consents", json={"scope": scope, "granted": granted, "language": "en"}, headers=h)
    assert r.status_code == 200, r.text


class FakeTTS:
    provider, model = "gemini", "fake-tts"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def speak(self, text, voice, language):
        self.calls.append((text, voice, language))
        if self.fail:
            raise llm.ModelError("down")
        return b"RIFF....WAVE"


def test_flag_is_off_by_default_and_config_says_so(client, monkeypatch):
    monkeypatch.delenv("NEUROTWIN_COMPANION", raising=False)
    h = login(client)
    cfg = client.get("/api/companion/config").json()
    assert cfg["enabled"] is False
    monkeypatch.setenv("NEUROTWIN_COMPANION", "1")
    assert client.get("/api/companion/config").json()["enabled"] is True


def test_config_is_for_participants_only_and_has_no_secrets(client, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_COMPANION", "1")
    login(client, "dr.layla")
    assert client.get("/api/companion/config").status_code == 404
    login(client, "fatima")
    body = client.get("/api/companion/config").text
    assert "key" not in body.lower() and "GEMINI" not in body
    cfg = json.loads(body)
    assert cfg["defaults"]["silence_ms"] >= 1500          # people pause to think: the default wait is generous
    assert set(cfg) >= {"enabled", "stt", "tts", "model", "defaults", "limits"}


def test_new_consent_scope_is_separate_and_revocable(client):
    h = login(client)
    cs = {c["scope"]: c for c in client.get("/api/consents").json()}
    assert cs["assistant_model"]["granted"] is False and cs["voice_recording"]["granted"] is False
    consent(client, h, "assistant_model")
    assert {c["scope"]: c for c in client.get("/api/consents").json()}["assistant_model"]["granted"] is True
    assert {c["scope"]: c for c in client.get("/api/consents").json()}["voice_recording"]["granted"] is False
    consent(client, h, "assistant_model", False)
    assert {c["scope"]: c for c in client.get("/api/consents").json()}["assistant_model"]["granted"] is False


def test_server_speech_needs_flag_provider_demo_account_and_consent(client, app, monkeypatch):
    h = login(client)
    body = {"text": "Hello", "language": "en"}
    monkeypatch.delenv("NEUROTWIN_COMPANION", raising=False)
    assert client.post("/api/voice/speak", json=body, headers=h).status_code == 404          # flag off
    monkeypatch.setenv("NEUROTWIN_COMPANION", "1")
    app.state.get_tts = lambda: None
    assert client.post("/api/voice/speak", json=body, headers=h).status_code == 503          # no provider configured
    tts = FakeTTS()
    app.state.get_tts = lambda: tts
    assert client.post("/api/voice/speak", json=body, headers=h).status_code == 403          # no consent yet
    assert tts.calls == []
    consent(client, h, "assistant_model")
    r = client.post("/api/voice/speak", json=body, headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.headers["cache-control"] == "no-store"
    assert tts.calls == [("Hello", "Achird", "en")]
    consent(client, h, "assistant_model", False)
    assert client.post("/api/voice/speak", json=body, headers=h).status_code == 403          # revoked: stops at once


def test_real_participants_text_is_never_sent_to_a_speech_provider(client, app, monkeypatch, db_session=None):
    from sqlalchemy import select
    from app.models import User
    monkeypatch.setenv("NEUROTWIN_COMPANION", "1")
    tts = FakeTTS()
    app.state.get_tts = lambda: tts
    h = login(client)
    consent(client, h, "assistant_model")
    with app.state.db.SessionLocal() as db:
        u = db.get(User, "demo-fatima")
        u.is_demo = False
        db.commit()
    r = client.post("/api/voice/speak", json={"text": "Take your tablet", "language": "en"}, headers=h)
    assert r.status_code == 403 and tts.calls == []
    cfg = client.get("/api/companion/config").json()
    assert cfg["tts"]["server"] is False and cfg["tts"]["why_not"] == "real_data_stays_here"


def test_provider_failure_is_an_honest_error_and_is_audited_without_words(client, app, monkeypatch):
    from sqlalchemy import select
    from app.models import AuditEvent
    monkeypatch.setenv("NEUROTWIN_COMPANION", "1")
    app.state.get_tts = lambda: FakeTTS(fail=True)
    h = login(client)
    consent(client, h, "assistant_model")
    r = client.post("/api/voice/speak", json={"text": "Secret words here", "language": "en"}, headers=h)
    assert r.status_code == 502 and "could not be used" in r.json()["detail"]
    with app.state.db.SessionLocal() as db:
        rows = [(a.action, a.target) for a in db.scalars(select(AuditEvent))]
    assert any(a == "companion.speech_failed" for a, _ in rows)
    assert not any("Secret" in str(d) for _, d in rows)


def test_speak_limits_and_validation(client, app, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_COMPANION", "1")
    app.state.get_tts = lambda: FakeTTS()
    h = login(client)
    consent(client, h, "assistant_model")
    assert client.post("/api/voice/speak", json={"text": "x" * 601, "language": "en"}, headers=h).status_code == 422
    assert client.post("/api/voice/speak", json={"text": "  ", "language": "en"}, headers=h).status_code == 422
    monkeypatch.setenv("NEUROTWIN_TTS_DAILY_CALLS", "1")
    COMP._calls.update(day=None, n=0)
    assert client.post("/api/voice/speak", json={"text": "one", "language": "en"}, headers=h).status_code == 200
    assert client.post("/api/voice/speak", json={"text": "two", "language": "en"}, headers=h).status_code == 429


def test_gemini_speech_request_and_response_shape_with_a_mocked_transport():
    seen = {}

    def handler(req: httpx.Request):
        seen["path"], seen["body"] = req.url.path, json.loads(req.content)
        pcm = (b"\x01\x00" * 24)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]})

    c = llm.GeminiClient("k", "tts-model", transport=httpx.MockTransport(handler))
    wav = c.speak("Good morning", "SomeVoice", "en")
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE" and len(wav) == 44 + 48
    assert seen["path"].endswith("/models/tts-model:generateContent")
    assert seen["body"]["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert seen["body"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "SomeVoice"
    bad = llm.GeminiClient("k", "tts-model", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"candidates": []})))
    with pytest.raises(llm.ModelError):
        bad.speak("x", None, "en")


def test_tts_client_needs_a_key_and_defaults_to_the_documented_speech_model():
    assert llm.get_tts_client({}) is None
    assert llm.get_tts_client({"GEMINI_TTS_MODEL": "m"}) is None
    assert llm.get_tts_client({"GEMINI_API_KEY": "k"}).model == llm.DEFAULT_TTS_MODEL == "gemini-3.8-flash-tts"
    assert llm.get_tts_client({"GEMINI_API_KEY": "k", "GEMINI_TTS_MODEL": "m"}).model == "m"


def test_a_ready_made_wav_is_passed_through_and_a_rejected_style_is_retried_in_plain_form():
    wav = llm._wav(b"\x01\x00" * 24, 24000)
    calls = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        calls.append(body)
        if "speech_metadata" in body["contents"][0]["parts"][0]:
            return httpx.Response(400, json={"error": "unknown field"})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(wav).decode()}}]}}]})

    out = llm.GeminiClient("k", "m", transport=httpx.MockTransport(handler)).speak("Hello", "Achird", "en")
    assert out == wav and len(calls) == 2 and "speech_metadata" not in calls[1]["contents"][0]["parts"][0]
    assert calls[1]["contents"][0]["parts"][0]["text"].endswith("Hello")
