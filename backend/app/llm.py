"""Model providers behind one small interface.

The rest of the app asks for text and gets text back; it never knows which provider answered. Two providers:

- Gemini      Google's Generative Language API. Key in the `x-goog-api-key` header, never in the URL.
- Meta        Meta's Model API, OpenAI-style chat completions with a Bearer key.

Rules this module keeps:
- Keys come from the environment (or backend/.env) and never leave the server. They are not logged, and an error
  raised from here carries the provider name and HTTP status only, never the request, the key or the reply body.
- A provider with no key or no model id is simply "not configured": callers get None and say so. Nothing is faked.
- Only synthetic demo data may be sent until a provider and region are approved for real health data.

The request shapes follow each provider's public REST API. Until `scripts/list_models.py` and a live call have been
run with real keys, treat them as unverified: the tests here use a stand-in transport and prove the plumbing only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
META_BASE_DEFAULT = "https://api.meta.ai/v1"
TIMEOUT_S = 120.0


class ModelError(RuntimeError):
    """A provider call failed. The message is safe to show and log."""


@dataclass
class Reply:
    text: str
    provider: str
    model: str


def _raise(provider: str, exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        raise ModelError(f"{provider} answered HTTP {exc.response.status_code}.") from None
    raise ModelError(f"{provider} could not be reached ({type(exc).__name__}).") from None


class GeminiClient:
    provider = "gemini"

    def __init__(self, api_key: str, model: str | None, transport: httpx.BaseTransport | None = None):
        self.model = (model or "").removeprefix("models/")
        self._http = httpx.Client(base_url=GEMINI_BASE, timeout=TIMEOUT_S, transport=transport,
                                  headers={"x-goog-api-key": api_key})

    def list_models(self) -> list[str]:
        """Model ids this key can use for text generation."""
        try:
            r = self._http.get("/models", params={"pageSize": 200})
            r.raise_for_status()
            return sorted(m["name"].removeprefix("models/") for m in r.json().get("models", [])
                          if "generateContent" in m.get("supportedGenerationMethods", []))
        except (httpx.HTTPError, KeyError, ValueError) as e:
            _raise("Gemini", e)

    def complete(self, system: str, user: str, json_mode: bool = False) -> Reply:
        body = {"system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.2}}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        try:
            r = self._http.post(f"/models/{self.model}:generateContent", json=body)
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            return Reply("".join(p.get("text", "") for p in parts), self.provider, self.model)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            _raise("Gemini", e)


class MetaClient:
    provider = "meta"

    def __init__(self, api_key: str, model: str | None, base_url: str | None = None,
                 transport: httpx.BaseTransport | None = None):
        self.model = model or ""
        self._http = httpx.Client(base_url=(base_url or META_BASE_DEFAULT).rstrip("/"), timeout=TIMEOUT_S,
                                  transport=transport, headers={"Authorization": f"Bearer {api_key}"})

    def list_models(self) -> list[str]:
        try:
            r = self._http.get("/models")
            r.raise_for_status()
            return sorted(m["id"] for m in r.json().get("data", []))
        except (httpx.HTTPError, KeyError, ValueError) as e:
            _raise("Meta", e)

    def complete(self, system: str, user: str, json_mode: bool = False) -> Reply:
        body = {"model": self.model, "temperature": 0.2,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = self._http.post("/chat/completions", json=body)
            r.raise_for_status()
            return Reply(r.json()["choices"][0]["message"]["content"] or "", self.provider, self.model)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            _raise("Meta", e)


def clients(env: dict | None = None) -> dict:
    """Every provider that has a key, whether or not a model has been chosen yet (used to list models)."""
    env = os.environ if env is None else env
    out = {}
    if env.get("GEMINI_API_KEY"):
        out["gemini"] = GeminiClient(env["GEMINI_API_KEY"], env.get("GEMINI_MODEL"))
    if env.get("META_API_KEY"):
        out["meta"] = MetaClient(env["META_API_KEY"], env.get("META_MODEL"), env.get("META_API_BASE_URL"))
    return out


def get_client(env: dict | None = None):
    """The provider chosen by NEUROTWIN_AI_PROVIDER, or None when it has no key or no model id."""
    env = os.environ if env is None else env
    chosen = (env.get("NEUROTWIN_AI_PROVIDER") or "").strip().lower()
    client = clients(env).get(chosen)
    return client if client is not None and client.model else None


def status(env: dict | None = None) -> dict:
    """What is configured, for the app to show. Names and booleans only: never a key."""
    env = os.environ if env is None else env
    active = get_client(env)
    return {"provider": active.provider if active else None, "model": active.model if active else None,
            "configured": active is not None,
            "keys_present": {"gemini": bool(env.get("GEMINI_API_KEY")), "meta": bool(env.get("META_API_KEY"))}}
