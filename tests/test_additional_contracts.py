import asyncio
import base64
import io
import wave

import httpx
from conftest import sign_in

from app.ai import Gateway
from app.config import settings


def test_tts_pcm_to_wav(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "test-only")

    def handler(req):
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/L16;codec=pcm;rate=24000",
                                        "data": base64.b64encode(
                                            b"\x00\x00" * 240
                                        ).decode(),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    data = asyncio.run(
        Gateway(httpx.MockTransport(handler)).synthesize("Synthetic greeting")
    )
    with wave.open(io.BytesIO(data)) as w:
        assert (
            w.getframerate() == 24000
            and w.getnchannels() == 1
            and w.getnframes() == 240
        )


def test_cross_origin_mutation_denied(client):
    sign_in(client)
    r = client.post(
        "/api/patients/patient-demo/preferences",
        json={"text_size": "large"},
        headers={"Origin": "https://foreign.invalid"},
    )
    assert r.status_code == 403


def test_agent_registry_and_meta_draft_unavailable(client):
    sign_in(client, "clinician")
    assert len(client.get("/api/agents").json()["roles"]) == 8
    c = client.post(
        "/api/patients/patient-demo/concerns",
        json={"command_id": "draft-test-command", "text": "A synthetic concern"},
    ).json()
    r = client.post(f"/api/patients/patient-demo/cases/{c['id']}/evidence-draft")
    assert r.status_code == 503
