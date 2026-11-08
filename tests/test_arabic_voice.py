import asyncio
import json

import httpx
import pytest

from app.ai import Gateway, ProviderUnavailable, gateway
from app.config import ROOT, settings
from tests.conftest import sign_in


def test_provider_contract_and_redacted_failure(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "test-only-not-a-real-key")

    def handler(request):
        body = json.loads(request.content)
        assert "inlineData" in body["contents"][0]["parts"][1]
        assert "Preserve negation" in body["contents"][0]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": json.dumps({"text": "لا تفتح الإعدادات"})}
                            ]
                        }
                    }
                ]
            },
        )

    assert (
        asyncio.run(
            Gateway(httpx.MockTransport(handler)).transcribe_arabic(
                b"synthetic-audio", "audio/wav"
            )
        )
        == "لا تفتح الإعدادات"
    )

    def forbidden(request):
        return httpx.Response(429, json={"secret": "provider private message"})

    with pytest.raises(ProviderUnavailable) as error:
        asyncio.run(
            Gateway(httpx.MockTransport(forbidden)).transcribe_arabic(
                b"wave", "audio/wav"
            )
        )
    assert "private" not in str(error.value) and "key" not in str(error.value)


def test_arabic_upload_explicit_route_and_transcript_only(client, monkeypatch):
    from tests.test_companion import wav_bytes

    sign_in(client)
    called = []

    async def arabic(audio, mime):
        called.append("gemini")
        return "افتح الإعدادات"

    async def english(*args):
        raise AssertionError("Arabic audio must not silently use Meta")

    monkeypatch.setattr(gateway, "transcribe_arabic", arabic)
    monkeypatch.setattr(gateway, "transcribe", english)
    response = client.post(
        "/api/patients/patient-demo/voice/transcribe",
        data={"locale": "ar"},
        files={"audio": ("sample.wav", wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["source"] == "gemini_arabic_transcribe"
        and response.json()["audio_retained"] is False
    )
    assert called == ["gemini"] and "intent" not in response.json()


def test_catalog_safety_copy_and_schema():
    catalog = json.loads(
        (ROOT / "web/dashboard/ar-catalog.json").read_text(encoding="utf-8")
    )
    assert len(catalog) > 1000
    assert all(
        isinstance(k, str) and isinstance(v, str) and v.strip()
        for k, v in catalog.items()
    )
    for key in [
        "These research activities remain English-only. Changing the app language does not translate the assessment.",
        "Arabic voice is unavailable on this device. You can read the text or type instead.",
        "Saving a concern does not contact an emergency service or guarantee an immediate response.",
    ]:
        assert any(
            word in catalog[key] for word in ["لا", "لم", "غير", "ليس", "دون", "لن"]
        )
