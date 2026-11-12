"""Runtime shared by every AI agent of Agent Analysis: provider choice, the egress log, the trace store and a daily cap.

What this module guarantees (the agents themselves come later):
- A model is called only through `invoke`. Before the call it writes an egress record (what kind of data, which fact ids,
  how many characters, to which provider); after the call it writes a trace record. Both are append-only files in the run folder
  (`egress.jsonl`, `agents.jsonl`) and hold no keys.
- Only text built by `serialise` leaves: the ledger facts an agent was given. Nothing else of the run is sent. Images are sent only
  when NEUROTWIN_AGENTS_SEND_IMAGES=1 is set, and each image is named in the egress record.
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


SCRIPTED_EXPLAIN_AR = [("تمت مقارنة فحصين للشخص نفسه. نص تجريبي مبرمج.", "F-interval"), ("لم تُقدَّر بعدُ درجة عدم اليقين في القياسات. نص تجريبي مبرمج.", "F-uncertainty")]
SCRIPTED_FAMILY_AR = [("تمت مقارنة فحصين للشخص نفسه، أُجريا بفارق زمني بينهما.", "F-interval"),
                       ("لا نعرف بعدُ مدى دقة القياسات.", "F-uncertainty"),
                       ("سيشرح لكم الطبيب معنى ذلك. نص تجريبي مبرمج.", "F-uncertainty")]
SCRIPTED_AR = {
    SCRIPTED_EXPLAIN_AR[0][0]: "Two scans of the same person were compared. Scripted demo text.",
    SCRIPTED_EXPLAIN_AR[1][0]: "How reliable the measurements are has not been estimated yet. Scripted demo text.",
    SCRIPTED_FAMILY_AR[0][0]: "Two scans of the same person were compared, taken some time apart.",
    SCRIPTED_FAMILY_AR[1][0]: "We do not yet know how accurate the measurements are.",
    SCRIPTED_FAMILY_AR[2][0]: "The doctor will explain what this means. Scripted demo text.",
}


class MockClient:
    """Scripted stand-in for demos without keys. It restates the first facts it is given and says so; it understands nothing."""
    model = "scripted-demo"

    def __init__(self, provider: str):
        self.provider = f"mock-{provider}"

    def complete(self, system: str, user: str, json_mode: bool = False, images: list[bytes] | None = None) -> llm.Reply:
        ids = [ln.split(":")[0] for ln in user.splitlines() if ln.startswith("F-")]
        if "QUALITY_REVIEWER" in system:
            c = [i for i in ("F-interval", "F-uncertainty", "F-align") if i in ids] or ids[:1]
            return llm.Reply(json.dumps({"verdict": "proceed", "statements": [{"text": f"Scripted demo statement {chr(97 + k)}: see fact {i}.", "cites": [i]} for k, i in enumerate((c * 3)[:3])]}), self.provider, self.model)
        if "FINDINGS_CHALLENGER" in system:
            c = [i for i in ("F-uncertainty", "F-total") if i in ids] or ids[:1]
            return llm.Reply(json.dumps({"doubts": [{"text": f"Scripted demo doubt {chr(97 + k)}: see fact {i}.", "cites": [i]} for k, i in enumerate((c * 3)[:3])],
                                         "questions": [{"text": f"Scripted demo question {chr(97 + k)}: what does fact {i} leave open?", "cites": [i]} for k, i in enumerate((c * 2)[:2])]}), self.provider, self.model)
        if "BACK_TRANSLATOR" in system:  # scripted: only the scripted Arabic lines below are known; nothing is really translated
            n = user.count("Statement ")
            return llm.Reply(json.dumps({"texts": [SCRIPTED_AR.get(ln.split(": ", 1)[1].strip(), "Scripted demo: no translation was made.")
                                                    for ln in user.splitlines() if ln.startswith("Statement ") and ": " in ln][:n]}), self.provider, self.model)
        if "FAMILY_SUMMARY" in system and "ARABIC_OUTPUT" in system:
            return llm.Reply(json.dumps({"statements": [{"text": t, "cites": [c]} for t, c in SCRIPTED_FAMILY_AR]}), self.provider, self.model)
        if "FAMILY_SUMMARY" in system:
            return llm.Reply(json.dumps({"statements": [
                {"text": "Two scans of the same person, taken some time apart, were compared by the care team.", "cites": ["F-interval"]},
                {"text": "How reliable the measurements are is not known yet.", "cites": ["F-uncertainty"]},
                {"text": "The clinician will talk through what this means with you. Scripted demo text.", "cites": ["F-uncertainty"]}]}), self.provider, self.model)
        if "FOLLOWUP_PLANNER" in system:
            c = [i for i in ids if i.startswith(("F-limit", "F-uncertainty"))][:3] or ids[:1]
            return llm.Reply(json.dumps({"items": [{"text": f"Consider reading the matching limitation next to the scans. Scripted demo item {chr(97 + k)}.", "cites": [i]} for k, i in enumerate((c * 3)[:3])]}), self.provider, self.model)
        if "EVIDENCE_TOOLS" in system:
            return llm.Reply(json.dumps({"tools": [{"name": "get_interval", "arg": ""}, {"name": "get_limitations", "arg": ""}]}), self.provider, self.model)
        if "EVIDENCE_ANSWER" in system:
            return llm.Reply(json.dumps({"answer": [{"text": t[:280], "cites": [i]} for i, t in [ln.split(": ", 1) for ln in user.splitlines() if ln.startswith("F-")][:2]], "note": ""}), self.provider, self.model)
        if "VISUAL_OBSERVER" in system:  # A9: one scripted impression at the centre of the first slice, matched to the first region fact in the prompt
            ids = [ln.split(":")[0] for ln in user.splitlines() if ln.startswith("F-R")]
            obs = [{"slice": "S1", "x": 0.5, "y": 0.5, "description": "Scripted demo marker, placed in the middle of the first slice. No image was looked at.", "region": ids[0], "cites": [ids[0]]}] if ids else []
            return llm.Reply(json.dumps({"observations": obs}), self.provider, self.model)
        if "VISUAL_CHECKER" in system:
            n = user.count("Observation ")
            return llm.Reply(json.dumps({"checks": [{"index": i, "verdict": "agreed", "reason": "Scripted demo: no check was made."} for i in range(n)]}), self.provider, self.model)
        if "independent checker" in system:  # A4: a scripted stand-in cannot judge anything, and says so
            n = user.count("Statement ")
            return llm.Reply(json.dumps({"checks": [{"index": i, "supported": True, "reason": "Scripted demo: no check was made."} for i in range(n)]}), self.provider, self.model)
        if "ARABIC_OUTPUT" in system:
            keep = [i for i in ("F-interval", "F-uncertainty") if i in ids]
            return llm.Reply(json.dumps({"statements": [{"text": t, "cites": [c]} for t, c in SCRIPTED_EXPLAIN_AR if c in keep]}), self.provider, self.model)
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


def images_allowed(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return env.get("NEUROTWIN_AGENTS_SEND_IMAGES") == "1"


def invoke(run_dir: Path, agent: str, provider: str, system: str, user: str, fact_ids: list[str], json_mode: bool = True,
           attempt: int = 1, client=None, env: dict | None = None, images: list[tuple[str, bytes]] | None = None) -> dict:
    """One model call with its egress and trace records. Returns {status, text, provider, model, reason}; status is
    completed, unavailable or failed. `client` may be passed in (tests); otherwise it comes from the mode and keys."""
    c = client if client is not None else client_for(provider, env)
    base = {"agent": agent, "attempt": attempt}
    if c is None:
        _append(run_dir, TRACE, {**base, "provider": provider, "model": None, "status": "unavailable", "reason": f"No {provider} provider is configured on this server (mode {mode(env)})."})
        return {"status": "unavailable", "text": None, "provider": provider, "model": None, "reason": f"No {provider} provider is configured on this server."}
    mock0 = c.provider.startswith("mock")
    if images and not mock0 and not images_allowed(env):  # defence in depth: images never leave unless the owner switched them on
        _append(run_dir, TRACE, {**base, "provider": c.provider, "model": c.model, "status": "unavailable", "reason": "Sending images to a model is switched off (NEUROTWIN_AGENTS_SEND_IMAGES)."})
        return {"status": "unavailable", "text": None, "provider": c.provider, "model": c.model, "reason": "Sending scan images to a model is switched off on this server."}
    if not _take_call(env):
        _append(run_dir, TRACE, {**base, "provider": c.provider, "model": c.model, "status": "unavailable", "reason": "Daily agent call limit reached."})
        return {"status": "unavailable", "text": None, "provider": c.provider, "model": c.model, "reason": "Today's limit for agent calls has been reached."}
    mock = c.provider.startswith("mock")
    _append(run_dir, EGRESS, {"agent": agent, "provider": c.provider, "model": c.model, "data": "ledger facts (text)", "fact_ids": fact_ids,
                              "chars": len(system) + len(user), "images": len(images or []), "image_names": [n for n, _ in images or []],
                              "image_bytes": sum(len(b) for _, b in images or []), "sent_outside": not mock})
    t0 = time.monotonic()
    sha = hashlib.sha256((system + "\n" + user).encode()).hexdigest()[:16]
    try:
        reply = c.complete(system, user, json_mode=json_mode, **({"images": [b for _, b in images]} if images else {}))
    except llm.ModelError as e:
        _append(run_dir, TRACE, {**base, "provider": c.provider, "model": c.model, "status": "failed", "reason": str(e), "prompt_sha256": sha, "ms": round(1000 * (time.monotonic() - t0))})
        return {"status": "failed", "text": None, "provider": c.provider, "model": c.model, "reason": str(e)}
    _append(run_dir, TRACE, {**base, "provider": c.provider, "model": c.model, "status": "completed", "prompt_sha256": sha, "chars_out": len(reply.text),
                             "ms": round(1000 * (time.monotonic() - t0)), "output": reply.text, "scripted": mock})
    return {"status": "completed", "text": reply.text, "provider": c.provider, "model": c.model, "reason": None}
