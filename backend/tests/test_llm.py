"""Plumbing only: these use a stand-in transport, so they say nothing about live model quality or availability."""
import json

import httpx
import pytest

from app import llm

KEY = "sk-test-SECRET-KEY-123"


def transport(handler):
    return httpx.MockTransport(handler)


def test_gemini_request_shape_and_key_placement():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "hello"}]}}]})

    c = llm.GeminiClient(KEY, "models/some-model", transport=transport(handler))
    r = c.complete("system text", "user text", json_mode=True)
    assert r.text == "hello" and r.provider == "gemini" and r.model == "some-model"
    assert seen["url"].endswith("/v1beta/models/some-model:generateContent") and KEY not in seen["url"]
    assert seen["headers"]["x-goog-api-key"] == KEY
    assert seen["body"]["system_instruction"]["parts"][0]["text"] == "system text"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_lists_only_text_generation_models():
    def handler(request):
        return httpx.Response(200, json={"models": [
            {"name": "models/b-text", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/a-text", "supportedGenerationMethods": ["generateContent", "countTokens"]},
            {"name": "models/embed", "supportedGenerationMethods": ["embedContent"]}]})
    assert llm.GeminiClient(KEY, None, transport=transport(handler)).list_models() == ["a-text", "b-text"]


def test_meta_request_shape():
    seen = {}

    def handler(request):
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    c = llm.MetaClient(KEY, "a-model", "https://example.test/v1/", transport=transport(handler))
    assert c.complete("s", "u").text == "hi"
    assert seen["url"] == "https://example.test/v1/chat/completions" and seen["auth"] == f"Bearer {KEY}"
    assert seen["body"]["model"] == "a-model" and seen["body"]["messages"][0] == {"role": "system", "content": "s"}


def test_meta_lists_models():
    handler = lambda request: httpx.Response(200, json={"data": [{"id": "z"}, {"id": "a"}]})
    assert llm.MetaClient(KEY, None, transport=transport(handler)).list_models() == ["a", "z"]


@pytest.mark.parametrize("make", [
    lambda t: llm.GeminiClient(KEY, "m", transport=t),
    lambda t: llm.MetaClient(KEY, "m", transport=t),
])
def test_errors_never_carry_the_key_or_the_reply(make):
    def refuse(request):
        return httpx.Response(403, text=f"bad key {KEY} PRIVATE-BODY")
    with pytest.raises(llm.ModelError) as e:
        make(transport(refuse)).complete("s", "u")
    assert "403" in str(e.value) and KEY not in str(e.value) and "PRIVATE-BODY" not in str(e.value)

    def down(request):
        raise httpx.ConnectError("no route")
    with pytest.raises(llm.ModelError) as e:
        make(transport(down)).complete("s", "u")
    assert KEY not in str(e.value)


def test_unexpected_reply_shape_is_a_model_error():
    handler = lambda request: httpx.Response(200, json={"candidates": []})
    with pytest.raises(llm.ModelError):
        llm.GeminiClient(KEY, "m", transport=transport(handler)).complete("s", "u")


def test_not_configured_means_none_not_a_fake():
    assert llm.get_client({}) is None
    assert llm.get_client({"NEUROTWIN_AI_PROVIDER": "gemini"}) is None                              # no key
    assert llm.get_client({"NEUROTWIN_AI_PROVIDER": "gemini", "GEMINI_API_KEY": KEY}) is None       # no model
    assert llm.get_client({"NEUROTWIN_AI_PROVIDER": "meta", "GEMINI_API_KEY": KEY, "GEMINI_MODEL": "m"}) is None
    c = llm.get_client({"NEUROTWIN_AI_PROVIDER": "Gemini", "GEMINI_API_KEY": KEY, "GEMINI_MODEL": "m"})
    assert c is not None and c.provider == "gemini"


def test_status_shows_names_and_booleans_only():
    s = llm.status({"NEUROTWIN_AI_PROVIDER": "meta", "META_API_KEY": KEY, "META_MODEL": "m"})
    assert s == {"provider": "meta", "model": "m", "configured": True, "keys_present": {"gemini": False, "meta": True}}
    assert KEY not in str(s)


def test_env_file_is_read_without_overriding_real_variables(tmp_path, monkeypatch):
    from app import config
    f = tmp_path / ".env"
    f.write_text('# comment\nNT_TEST_A=from-file\nNT_TEST_B="quoted value"\n\nnot a line\n', encoding="utf-8")
    monkeypatch.setenv("NT_TEST_A", "from-environment")
    monkeypatch.delenv("NT_TEST_B", raising=False)
    config.load_env(f)
    import os
    assert os.environ["NT_TEST_A"] == "from-environment" and os.environ["NT_TEST_B"] == "quoted value"
    monkeypatch.delenv("NT_TEST_B")


def test_status_endpoint_needs_sign_in_and_hides_keys(client, login, monkeypatch):
    assert client.get("/api/ai/status").status_code == 401
    monkeypatch.setenv("NEUROTWIN_AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setenv("GEMINI_MODEL", "m")
    r = client.get("/api/ai/status", headers=login("demo-dr-layla"))
    assert r.json()["configured"] is True and KEY not in r.text
