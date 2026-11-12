"""Runtime shared by every AI agent of Agent Analysis: provider choice, the egress log, the trace store and a daily cap.

What this module guarantees (the agents themselves come later):
- A model is called only through `invoke`. Before the call it writes an egress record (what kind of data, which fact ids,
  how many characters, to which provider); after the call it writes a trace record. Both are append-only files in the run folder
  (`egress.jsonl`, `agents.jsonl`) and hold no keys.
- Only text built by `serialise` leaves: the ledger facts an agent was given. Nothing else of the run is sent. Images are not
  sent by this module; that needs its own switch (NEUROTWIN_AGENTS_SEND_IMAGES=1) and its own agent.
- Modes (NEUROTWIN_AGENTS_MODE): "live" calls the configured providers, "mock" uses a scripted stand-in that restates facts and
  is labelled as such everywhere, "off" runs nothing. Unset means live when a key is configured, otherwise off. Mock is never
  chosen silently.
- A missing provider, a failed call or an exhausted daily cap gives a result with status "unavailable" or "failed". It never
  gives made-up text, and the rest of the run is untouched.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

from . import llm

VERSION = "agent-runtime/0.1"
EGRESS, TRACE = "egress.jsonl", "agents.jsonl"
ROLES = {"gemini": "drafts and explains", "meta": "checks independently"}
_cap = {"day": None, "n": 0}


def mode(env: dict | None = None) -> str:
    env = os.environ if env is None else env
    m = (env.get("NEUROTWIN_AGENTS_MODE") or "").strip().lower()
    if m in ("live", "mock", "off"):
        return m
    return "live" if (env.get("GEMINI_API_KEY") or env.get("META_API_KEY")) else "off"


class MockClient:
    """Scripted stand-in for demos without keys. It restates the first facts it is given and says so; it understands nothing."""
    model = "scripted-demo"

    def __init__(self, provider: str):
        self.provider = f"mock-{provider}"

    def complete(self, system: str, user: str, json_mode: bool = False) -> llm.Reply:
        rows = [ln.split(": ", 1) for ln in user.splitlines() if ln.startswith("F-") and ": " in ln]
        picks = [r for r in rows if r[0] in ("F-interval", "F-total", "F-uncertainty") or r[0].startswith("F-R")][:4]
        body = json.dumps({"statements": [{"text": t[:380], "cites": [i]} for i, t in picks]})
        return llm.Reply(body, self.provider, self.model)


def client_for(provider: str, env: dict | None = None):
    """The client for 'gemini' or 'meta' under the current mode, or None when it is not available."""
    env = os.environ if env is None else env
    m = mode(env)
    if m == "off":
        return None
    if m == "mock":
        return MockClient(provider)
    key = {"gemini": "GEMINI_API_KEY", "meta": "META_API_KEY"}[provider]
    if not env.get(key):
        return None
    pick = f"AGENTS_{provider.upper()}_MODEL"
    model = env.get(pick) or env.get(f"{provider.upper()}_MODEL")
    if provider == "gemini":
        c = llm.GeminiClient(env[key], model)
    else:
        c = llm.MetaClient(env[key], model, env.get("META_API_BASE_URL"))
    return c if c.model else None


def status(env: dict | None = None) -> dict:
    """Names and booleans only, never a key."""
    env = os.environ if env is None else env
    out = {"mode": mode(env), "version": VERSION, "daily_limit": daily_limit(env), "send_images": env.get("NEUROTWIN_AGENTS_SEND_IMAGES") == "1", "providers": {}}
    for p in ROLES:
        c = client_for(p, env)
        out["providers"][p] = {"role": ROLES[p], "available": c is not None, "provider": c.provider if c else None, "model": c.model if c else None}
    return out


def daily_limit(env: dict | None = None) -> int:
    env = os.environ if env is None else env
    try:
        return int(env.get("NEUROTWIN_AGENTS_DAILY_CALLS") or 150)
    except ValueError:
        return 150


def _take_call(env: dict | None = None) -> bool:
    today = date.today()
    if _cap["day"] != today:
        _cap["day"], _cap["n"] = today, 0
    if _cap["n"] >= daily_limit(env):
        return False
    _cap["n"] += 1
    return True


def serialise(ledger: dict, ids: list[str] | None = None) -> tuple[str, list[str]]:
    """The only text that may be sent: ledger facts (all, or the listed ids), one per line. Returns the text and the ids in it."""
    keep = [f for f in ledger["facts"] if ids is None or f["id"] in ids]
    return "Facts:\n" + "\n".join(f"{f['id']}: {f['text']}" for f in keep), [f["id"] for f in keep]


def _append(run_dir: Path, name: str, rec: dict) -> dict:
    path = run_dir / name
    seq = 1 + (sum(1 for _ in path.open("rb")) if path.exists() else 0)
    rec = {"seq": seq, "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **rec}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read(run_dir: Path, name: str) -> list[dict]:
    path = run_dir / name
    out = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass  # a half-written last line
    return out


def invoke(run_dir: Path, agent: str, provider: str, system: str, user: str, fact_ids: list[str], json_mode: bool = True,
           attempt: int = 1, client=None, env: dict | None = None) -> dict:
    """One model call with its egress and trace records. Returns {status, text, provider, model, reason}; status is
    completed, unavailable or failed. `client` may be passed in (tests); otherwise it comes from the mode and keys."""
    c = client if client is not None else client_for(provider, env)
    base = {"agent": agent, "attempt": attempt}
    if c is None:
        _append(run_dir, TRACE, {**base, "provider": provider, "model": None, "status": "unavailable", "reason": f"No {provider} provider is configured on this server (mode {mode(env)})."})
        return {"status": "unavailable", "text": None, "provider": provider, "model": None, "reason": f"No {provider} provider is configured on this server."}
    if not _take_call(env):
        _append(run_dir, TRACE, {**base, "provider": c.provider, "model": c.model, "status": "unavailable", "reason": "Daily agent call limit reached."})
        return {"status": "unavailable", "text": None, "provider": c.provider, "model": c.model, "reason": "Today's limit for agent calls has been reached."}
    mock = c.provider.startswith("mock")
    _append(run_dir, EGRESS, {"agent": agent, "provider": c.provider, "model": c.model, "data": "ledger facts (text)", "fact_ids": fact_ids,
                              "chars": len(system) + len(user), "images": 0, "sent_outside": not mock})
    t0 = time.monotonic()
    sha = hashlib.sha256((system + "\n" + user).encode()).hexdigest()[:16]
    try:
        reply = c.complete(system, user, json_mode=json_mode)
    except llm.ModelError as e:
        _append(run_dir, TRACE, {**base, "provider": c.provider, "model": c.model, "status": "failed", "reason": str(e), "prompt_sha256": sha, "ms": round(1000 * (time.monotonic() - t0))})
        return {"status": "failed", "text": None, "provider": c.provider, "model": c.model, "reason": str(e)}
    _append(run_dir, TRACE, {**base, "provider": c.provider, "model": c.model, "status": "completed", "prompt_sha256": sha, "chars_out": len(reply.text),
                             "ms": round(1000 * (time.monotonic() - t0)), "output": reply.text, "scripted": mock})
    return {"status": "completed", "text": reply.text, "provider": c.provider, "model": c.model, "reason": None}
