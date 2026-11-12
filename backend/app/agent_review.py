"""Clinician review of the AI drafts of one run: item decisions, approve or return, and a record of who did what and when.

State (stored in review.json, never inferred): `ai_drafts` (nothing decided) -> `in_review` (some items decided) -> `approved` or `returned`.
Items are the pieces that could leave the page: the explanation statements (A3), the follow-up suggestions (A6) and the drawn visual impressions (A9). An item's id
includes a hash of its text, so a regenerated draft is a new, undecided item. An approval records a fingerprint of the accepted items; if any draft is regenerated
afterwards the approval is shown as outdated and cannot be used for release. Approval covers the accepted AI items and the draft report, nothing else. It is the clinician's
decision, recorded under the clinician's own account, and not a clinical approval of any care.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import agent_activity as AC
from . import agent_explainer as X
from . import agent_followup as F
from . import agent_visual_ai as VA

FILE = "review.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _h(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:10]


def items(run_dir: Path) -> list[dict]:
    """Everything the clinician may decide on right now, with the text that would be shown."""
    out = []
    ai = X.load(run_dir)
    if ai and ai["explanation"]["status"] == "completed" and ai["qa"]["passed"]:
        out += [{"id": f"explanation:{_h(s['text'])}", "kind": "explanation", "text": s["text"], "cites": s["cites"]} for s in ai["explanation"]["statements"]]
    fu = F.load(run_dir)
    if fu and fu["status"] == "completed":
        out += [{"id": f"followup:{_h(s['text'])}", "kind": "followup", "text": s["text"], "cites": s["cites"]} for s in fu["items"]]
    vis = VA.load(run_dir)
    if vis and vis["observer"]["status"] == "completed":
        out += [{"id": f"visual:{_h(o['description'] + o['slice'])}", "kind": "visual", "text": o["description"], "cites": o["cites"], "slice": o["slice"]} for o in vis["observations"] if o.get("drawn")]
    return out


def load(run_dir: Path) -> dict:
    p = run_dir / FILE
    try:
        rec = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except ValueError:
        rec = None
    return rec or {"decisions": {}, "history": [], "approval": None}


def _save(run_dir: Path, rec: dict) -> None:
    tmp = run_dir / (FILE + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(run_dir / FILE)


def fingerprint(accepted: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(accepted)).encode()).hexdigest()[:16]


def view(run_dir: Path) -> dict:
    """Current state for the screen: items with decisions, counts, and whether an approval still matches what is on screen."""
    rec, its = load(run_dir), items(run_dir)
    dec = rec["decisions"]
    shown = [{**i, "decision": (dec.get(i["id"]) or {}).get("decision"), "decided_by": (dec.get(i["id"]) or {}).get("by"), "note": (dec.get(i["id"]) or {}).get("note", "")} for i in its]
    accepted = [i["id"] for i in shown if i["decision"] == "accepted"]
    undecided = [i["id"] for i in shown if i["decision"] is None]
    ap = rec["approval"]
    outdated = bool(ap and ap["fingerprint"] != fingerprint(accepted))
    state = "ai_drafts" if not any(dec.get(i["id"]) for i in shown) and not ap else "in_review"
    if ap and ap["decision"] == "approved":
        state = "approval_outdated" if outdated else "approved"
    elif ap and ap["decision"] == "returned":
        state = "returned"
    return {"state": state, "items": shown, "undecided": len(undecided), "accepted": len(accepted), "approval": ap, "approval_outdated": outdated, "history": rec["history"],
            "note": "Approval covers the accepted AI items and the draft report. It is a recorded decision by a clinician, not a clinical approval of any care."}


def decide_item(run_dir: Path, item_id: str, decision: str, who: str, note: str = "") -> dict:
    if decision not in ("accepted", "rejected", "cleared"):
        raise ValueError("Decision must be accepted, rejected or cleared.")
    if item_id not in {i["id"] for i in items(run_dir)}:
        raise ValueError("That item is not on this run any more.")
    rec = load(run_dir)
    if decision == "cleared":
        rec["decisions"].pop(item_id, None)
    else:
        rec["decisions"][item_id] = {"decision": decision, "by": who, "at": _now(), "note": note[:300]}
    rec["history"].append({"event": f"item_{decision}", "item": item_id, "by": who, "at": _now()})
    _save(run_dir, rec)
    return view(run_dir)


def decide(run_dir: Path, decision: str, who: str, comment: str = "") -> dict:
    """approve, return or reopen the whole review."""
    if decision not in ("approve", "return", "reopen"):
        raise ValueError("Decision must be approve, return or reopen.")
    v = view(run_dir)
    rec = load(run_dir)
    if decision == "approve":
        if v["undecided"]:
            raise ValueError(f"{v['undecided']} AI item(s) still have no decision. Accept or reject each one first.")
        acc = [i["id"] for i in v["items"] if i["decision"] == "accepted"]
        rec["approval"] = {"decision": "approved", "by": who, "at": _now(), "comment": comment[:500], "fingerprint": fingerprint(acc), "accepted": acc}
        node = ("completed", f"Approved by a clinician with {len(acc)} accepted AI item(s). A recorded decision, not a clinical approval of any care.")
    elif decision == "return":
        if not comment.strip():
            raise ValueError("Say what should change when you return the review.")
        rec["approval"] = {"decision": "returned", "by": who, "at": _now(), "comment": comment[:500], "fingerprint": None, "accepted": []}
        node = ("awaiting_review", "Returned by the clinician with a comment. Waiting for changes.")
    else:
        rec["approval"] = None
        node = ("awaiting_review", "Reopened. No approval is recorded.")
    rec["history"].append({"event": decision, "by": who, "at": _now(), "comment": comment[:500]})
    _save(run_dir, rec)
    AC.log(run_dir, "clinician_review", node[0], node[1], tool="Clinician (human)")
    return view(run_dir)


def approved(run_dir: Path) -> bool:
    return view(run_dir)["state"] == "approved"
