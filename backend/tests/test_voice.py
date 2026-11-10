"""Voice typing with a stand-in speech provider. Says nothing about live transcription quality."""
import base64
import json

import httpx
import pytest

from app import llm
from conftest import USERNAMES


class FakeSTT:
    provider, model = "fake", "fake-stt"

    def __init__(self, text="hello from voice"):
        self.text, self.calls = text, []

    def transcribe(self, audio, mime, language):
        self.calls.append((len(audio), mime, language))
        return llm.Reply(self.text, self.provider, self.model)


def sign_in(client, uid):
    r = client.post("/api/auth/demo-enter", json={"username": USERNAMES[uid]})
    return {"X-CSRF-Token": r.json()["csrf"]}


def post(client, h, body=b"\x1a\x45\xdf\xa3audio", mime="audio/webm;codecs=opus", language="en"):
    return client.post(f"/api/voice/transcribe?language={language}", content=body,
                       headers={**h, "Content-Type": mime})


def test_family_dictates_and_audio_is_not_stored(client, app):
    fake = FakeSTT()
    app.state.get_stt = lambda: fake
    h = sign_in(client, "demo-mariam")
    r = post(client, h, language="ar")
    assert r.status_code == 200 and r.json()["text"] == "hello from voice"
    assert fake.calls == [(len(b"\x1a\x45\xdf\xa3audio"), "audio/webm", "ar")]
    from sqlalchemy import inspect
    cols = {c["name"] for t in inspect(app.state.db.engine).get_table_names() for c in inspect(app.state.db.engine).get_columns(t)}
    assert not any("audio" in c for c in cols)


def test_not_configured(client, app):
    app.state.get_stt = lambda: None
    h = sign_in(client, "demo-mariam")
    assert post(client, h).status_code == 503
    assert client.get("/api/voice/status").json() == {"available": False, "provider": None}


def test_input_checks(client, app):
    app.state.get_stt = lambda: FakeSTT()
    h = sign_in(client, "demo-mariam")
    assert post(client, h, mime="text/plain").status_code == 415
    assert post(client, h, body=b"").status_code == 422
    assert post(client, h, language="fr").status_code == 422
    assert post(client, h, body=b"x" * 2_600_000).status_code == 413


def test_participant_needs_voice_consent(client, app):
    app.state.get_stt = lambda: FakeSTT()
    h = sign_in(client, "demo-fatima")
    assert post(client, h).status_code == 403
    client.post("/api/consents", json={"scope": "voice_recording", "granted": True, "language": "en"}, headers=h)
    assert post(client, h).status_code == 200


def test_requires_sign_in(client):
    assert client.post("/api/voice/transcribe", content=b"x", headers={"Content-Type": "audio/webm"}).status_code in (401, 403)


def test_daily_cap_and_audit_has_no_words(client, app, monkeypatch):
    from app import voice
    voice._calls.update(day=None, n=0)
    monkeypatch.setenv("NEUROTWIN_STT_DAILY_CALLS", "2")
    app.state.get_stt = lambda: FakeSTT("secret words spoken")
    h = sign_in(client, "demo-mariam")
    assert [post(client, h).status_code for _ in range(3)] == [200, 200, 429]
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        rows = db.query(AuditEvent).filter(AuditEvent.action.like("voice.%")).all()
        assert rows and all("secret" not in (r.target or "") for r in rows)


def test_provider_failure_is_a_clear_message(client, app):
    class Broken(FakeSTT):
        def transcribe(self, *a):
            raise llm.ModelError("Gemini answered HTTP 500.")
    app.state.get_stt = lambda: Broken()
    h = sign_in(client, "demo-mariam")
    r = post(client, h)
    assert r.status_code == 502 and "HTTP 500" in r.json()["detail"]


def test_gemini_transcribe_request_shape():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": " مرحبا "}]}}]})
    c = llm.GeminiClient("k", "m", transport=httpx.MockTransport(handler))
    r = c.transcribe(b"abc", "audio/webm", "ar")
    assert r.text == "مرحبا"
    parts = seen["body"]["contents"][0]["parts"]
    assert parts[1]["inline_data"] == {"mime_type": "audio/webm", "data": base64.b64encode(b"abc").decode()}
    assert "Arabic" in parts[0]["text"] and "Never translate" in parts[0]["text"]


def test_stt_uses_gemini_only():
    env = {"NEUROTWIN_AI_PROVIDER": "meta", "GEMINI_API_KEY": "k", "GEMINI_MODEL": "g", "META_API_KEY": "m"}
    assert llm.get_stt_client(env).provider == "gemini"          # even when Meta writes the text drafts
    assert llm.get_stt_client({**env, "GEMINI_MODEL": ""}) is None
    assert llm.get_stt_client({"META_API_KEY": "m"}) is None


def test_gemini_prompt_never_asks_for_translation():
    seen = {}

    def handler(request):
        seen["prompt"] = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})
    llm.GeminiClient("k", "m", transport=httpx.MockTransport(handler)).transcribe(b"a", "audio/wav", "ar")
    assert "Never translate" in seen["prompt"] and "in Arabic" not in seen["prompt"]
