import asyncio
import json

import httpx
import numpy as np
import pytest

from app.ai import Gateway, ProviderUnavailable
from app.config import settings
from app.numerics import estimate


def obs(t=0, value=0, quality="usable", mode="self"):
    return {
        "time_days": t,
        "value": value,
        "quality": quality,
        "protocol": "research-v1",
        "mode": mode,
    }


def test_abstention_and_protocol():
    assert estimate([obs()])["status"] == "insufficient_history"
    assert (
        estimate([obs(0), obs(7), obs(14, mode="assisted")])["status"]
        == "incompatible_protocol"
    )
    assert estimate([obs(0), obs(0), obs(14)])["status"] == "invalid_timestamps"
    assert (
        estimate([obs(0), obs(7), obs(14, quality="poor")])["status"]
        == "insufficient_history"
    )


def test_covariance_and_units():
    r = estimate([obs(0, 0.4), obs(30, 0.2), obs(90, 0.1), obs(180, -0.1)])
    p = np.array(r["covariance"])
    assert np.allclose(p, p.T)
    assert np.all(np.linalg.eigvalsh(p) > 0)
    assert r["interval"][0] < r["estimate"] < r["interval"][1]
    assert r["clinical_use"] is False and r["rci"] is not None


def test_gemini_wire_and_schema(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "test-only")

    def handler(req):
        assert req.headers["x-goog-api-key"] == "test-only"
        assert "responseJsonSchema" in json.loads(req.content)["generationConfig"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "intent": "navigate",
                                            "screen": "settings",
                                            "text_size": "normal",
                                            "explanation": "Open settings",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    g = Gateway(httpx.MockTransport(handler))
    r = asyncio.run(g.intent("settings"))
    assert r.screen == "settings"


def test_invalid_model_output_rejected(monkeypatch):
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
                                    "text": '{"intent":"prescribe","explanation":"take medicine"}'
                                }
                            ]
                        }
                    }
                ]
            },
        )

    with pytest.raises(ValueError):
        asyncio.run(Gateway(httpx.MockTransport(handler)).intent("dose"))


def test_meta_wire_and_contributor_block(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "meta_api_key", "test-only")

    def handler(req):
        body = json.loads(req.content)
        assert body["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"value":"ok"}'}}]}
        )

    g = Gateway(httpx.MockTransport(handler))
    assert asyncio.run(
        g.structured("meta", "muse-spark-1.3", "synthetic", {"type": "object"})
    ) == {"value": "ok"}
    with pytest.raises(ProviderUnavailable):
        asyncio.run(g.structured("meta", "muse-spark-1.3-contributor", "x", {}))


def test_provider_failure_redacted(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "not-a-real-secret")

    def handler(req):
        return httpx.Response(429, json={"error": "sensitive provider text"})

    with pytest.raises(ProviderUnavailable) as e:
        asyncio.run(Gateway(httpx.MockTransport(handler)).intent("x"))
    assert "sensitive" not in str(e.value) and "not-a-real-secret" not in str(e.value)


def test_transcription_multipart_contract(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "meta_api_key", "test-only")

    def handler(req):
        assert req.url.path == "/v1/asr/transcribe"
        assert b'name="request"' in req.content and b'name="audio"' in req.content
        return httpx.Response(200, json={"transcript": "Open settings", "turns": []})

    assert (
        asyncio.run(
            Gateway(httpx.MockTransport(handler)).transcribe(b"wave", "audio/wav")
        )
        == "Open settings"
    )
