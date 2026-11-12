"""Execution record for Agent Analysis: the workflow graph and an append-only event log per run.

Events are written from the same place the run record is written (``agent_analysis._write``), by comparing what each stage
reports now with the last status already logged. That keeps the log tied to what really ran: a stage that did not run has no
event, and a planned agent that is not connected is logged as unavailable, never as completed.

``events.jsonl`` lives beside ``run.json``. Each line is one event with a per-run sequence number, so a client that
reconnects asks for ``after=<last seq>`` and never loses or repeats history. Runs saved before this log existed have no
events; they show their stored final state only and say so.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

TERMINAL = {"completed", "completed_with_warnings", "failed", "blocked", "unavailable", "cancelled", "skipped", "awaiting_review"}
STATUSES = ["waiting", "queued", "running", "completed", "completed_with_warnings", "failed", "blocked", "unavailable", "cancelled",
            "skipped", "awaiting_review"]
STEP_STATUS = {"pending": "waiting", "running": "running", "done": "completed", "warning": "completed_with_warnings", "failed": "failed",
               "blocked": "blocked", "unavailable": "unavailable", "cancelled": "cancelled"}
RUN_STATUS = {"queued": "queued", "running": "running", "aligned": "running", "complete": "completed", "partial": "completed_with_warnings",
              "failed": "failed", "cancelled": "cancelled", "blocked": "blocked", "unavailable": "unavailable"}
BUSY = ("queued", "running", "aligned")
ANALYSIS_STEPS = ("quality_review", "anatomical_analysis", "longitudinal_comparison", "findings_review", "report")

PLANNED = "Planned agent from docs/AGENT_ANALYSIS_AI_AGENTS.md. It is not connected: this run calls no language model."

# kind: tool = ordinary software step, ai = model-assisted agent, human = review gate. implemented=False means it is not built.
NODES = [
    {"id": "pair_validation", "step": "pair_validation", "kind": "tool", "label": "Scan-pair selection and identity validation", "deps": [],
     "role": "Checks both visits belong to one person, are in time order, and that the gap is near 12, 15 or 18 months."},
    {"id": "technical_checks", "step": None, "kind": "tool", "label": "Technical scan checks", "deps": ["pair_validation"],
     "role": "Reads each scan's header and intensities: shape, voxel size, range and coverage."},
    {"id": "alignment", "step": "alignment", "kind": "tool", "label": "Image preparation and alignment", "deps": ["technical_checks"],
     "role": "Rigidly aligns the later scan to the earlier scan (mutual information). Originals are never written to."},
    {"id": "brain_extraction", "step": None, "kind": "tool", "label": "Brain extraction", "deps": ["alignment"], "implemented": False,
     "role": "Would produce a brain mask.",
     "unavailable": "No separate brain-extraction tool is installed. The segmentation step works on the whole head, so no brain mask is made."},
    {"id": "quality_review", "step": "quality_review", "kind": "tool", "label": "Quality review", "deps": ["alignment"],
     "role": "Per-scan range and coverage, plus how well the alignment fit. Rule-based, no model."},
    {"id": "anatomical_analysis", "step": "anatomical_analysis", "kind": "tool", "label": "Segmentation import", "deps": ["alignment"],
     "role": "Imports SynthSeg regions made outside NeuroTwin for both scans and carries the later labels onto the earlier anatomy."},
    {"id": "longitudinal_comparison", "step": "longitudinal_comparison", "kind": "tool", "label": "Regional measurements and comparison",
     "deps": ["anatomical_analysis"], "role": "Counts each region's volume in both scans and the difference between them."},
    {"id": "findings_review", "step": "findings_review", "kind": "tool", "label": "Findings review", "deps": ["longitudinal_comparison"],
     "role": "Fixed rules mark each difference uncertain, small or inconsistent. Rule-based, no model."},
    {"id": "report", "step": "report", "kind": "tool", "label": "Draft report", "deps": ["findings_review", "quality_review"],
     "role": "A template restates the measurements. No language model writes it."},
    {"id": "quality_review_ai", "step": None, "kind": "ai", "label": "Quality reviewer (agent)", "deps": ["quality_review"], "ai_node": True,
     "role": "A model (Gemini) says in words whether the pair is fit to compare. A fixed rule gate sets the least cautious verdict it may give.", "unavailable": PLANNED},
    {"id": "findings_challenge", "step": None, "kind": "ai", "label": "Findings challenger (agent)", "deps": ["findings_review"], "ai_node": True,
     "role": "A model (Gemini) argues against over-reading: reasons a difference may be noise or processing, and questions for the clinician. It never calls a change real.", "unavailable": PLANNED},
    {"id": "ask_evidence", "step": None, "kind": "ai", "label": "Ask the evidence (agent)", "deps": ["report"], "ai_node": True,
     "role": "Answers a clinician's question from read-only lookups in this run's numbered facts. Refuses diagnosis, prediction, norms and treatment questions before any model is called.", "unavailable": PLANNED},
    {"id": "visual_comparison", "step": None, "kind": "ai", "label": "Visual comparison (agent)", "deps": ["longitudinal_comparison"], "ai_node": True,
     "role": "A model (Gemini) looks at the same slices of both scans and points at visible differences; rules check every pointer and a second model (Meta) cross-checks. Only with image sending switched on. Impressions are drawn apart from measured change.",
     "unavailable": PLANNED},
    {"id": "evidence_explanation", "step": None, "kind": "ai", "label": "Evidence explanation (agent)", "deps": ["report"], "ai_node": True,
     "role": "A language model (Gemini) drafts an explanation of the measured changes. Every sentence cites numbered facts and a rule-based checker refuses added numbers or claims. English only so far; a draft for clinician review.", "unavailable": PLANNED},
    {"id": "report_review_ai", "step": None, "kind": "ai", "label": "Report review (agent)", "deps": ["evidence_explanation"], "ai_node": True,
     "role": "A second model (Meta) judges each statement against the facts it cites, then fixed rules gate the draft for forbidden wording and missing limits.", "unavailable": PLANNED},
    {"id": "clinician_review", "step": None, "kind": "human", "label": "Clinician review", "deps": ["report"],
     "role": "A clinician reads the draft report and the evidence behind it. Nothing here is approved until a person does so."},
]
BY_ID = {n["id"]: n for n in NODES}
LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _path(run_dir: Path) -> Path:
    return run_dir / "events.jsonl"


def read_events(run_dir: Path, after: int = 0) -> list[dict]:
    p = _path(run_dir)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue  # a half-written last line is ignored until it is complete
        if e["seq"] > after:
            out.append(e)
    return out


def _ai_current(run: dict, step_state: dict, run_dir: Path | None, ended_early: bool) -> tuple[str, str]:
    """Agent nodes keep the status their own last event recorded; before any call they are waiting, unavailable (agents off) or skipped."""
    if step_state["report"] not in ("done", "warning"):
        return ("skipped", "Not run: the report was not produced.") if ended_early or run["state"] == "partial" else ("waiting", "Waits for the draft report.")
    if run_dir is not None:
        for e in reversed(read_events(run_dir)):
            if e["node"] == run["_ai_node"] and e["type"] == "status" and e.get("origin") == "agent":
                return e["status"], e["summary"]
    from . import agent_runtime as R
    if R.mode() == "off":
        return "unavailable", "No model provider is configured on this server, so this agent did not run."
    return "waiting", "Not run yet. A clinician asks for the AI explanation to run it."


def _current(run: dict, step_state: dict, run_dir: Path | None = None) -> dict:
    """Status and one-line summary for every node, from the run record as it stands now."""
    state = run["state"]
    ended_early = state in ("failed", "cancelled", "blocked", "unavailable")
    out = {}
    for n in NODES:
        nid = n["id"]
        if n.get("implemented") is False:
            out[nid] = ("unavailable", n["unavailable"])
            continue
        if n.get("ai_node"):
            out[nid] = _ai_current({**run, "_ai_node": nid}, step_state, run_dir, ended_early)
            continue
        if nid == "technical_checks":
            v = run["validation"]
            if v["status"] == "blocked":
                out[nid] = ("skipped", "Not run: the pair did not pass validation.")
            else:
                problems = [p for k in ("earlier", "later") for p in (v["checks"].get(k) or {}).get("problems", [])]
                out[nid] = ("completed_with_warnings", "; ".join(problems)) if problems else ("completed", "Headers and intensity ranges read for both scans.")
            continue
        if nid == "clinician_review":
            if step_state["report"] in ("done", "warning"):
                out[nid] = ("awaiting_review", "The draft report is waiting for a clinician. No approval has been recorded, and approval is not yet built into this prototype.")
            elif ended_early or state in ("partial",):
                out[nid] = ("skipped", "Nothing to review: the report was not produced.")
            else:
                out[nid] = ("waiting", "Waits for the draft report.")
            continue
        step = next(s for s in run["steps"] if s["key"] == n["step"])
        status = STEP_STATUS.get(step["state"], "waiting")
        summary = step["detail"]
        if status == "waiting" and nid == "alignment" and state == "queued":
            status = "queued"
        if status == "unavailable" and nid in ANALYSIS_STEPS and state in BUSY:
            status, summary = "waiting", "Waits for the earlier steps."
        elif status in ("waiting", "unavailable") and ended_early and nid != "pair_validation":
            status, summary = "skipped", {"failed": "Not run: an earlier step failed.", "cancelled": "Not run: the analysis was cancelled.",
                                          "blocked": "Not run: the pair did not pass validation.", "unavailable": "Not run: alignment is unavailable."}[state]
        elif status == "waiting":
            summary = "Waits for the earlier steps."
        out[nid] = (status, summary or "")
    return out


def sync(run_dir: Path, run: dict) -> None:
    """Append an event for every node whose status or summary changed since the last event, plus run-level and hand-off events."""
    step_state = {s["key"]: s["state"] for s in run["steps"]}
    cur = _current(run, step_state, run_dir)
    run_status = RUN_STATUS.get(run["state"], "waiting")
    with LOCK:
        events = read_events(run_dir)
        last: dict = {}
        for e in events:
            if e["type"] in ("status", "run"):
                last[e["node"]] = (e["status"], e["summary"])
        seq = events[-1]["seq"] if events else 0
        new = []

        def add(node, type_, status, summary, **extra):
            nonlocal seq
            seq += 1
            new.append({"seq": seq, "id": f"{run['run_id']}:{seq}", "run_id": run["run_id"], "node": node, "type": type_, "ts": now(),
                        "status": status, "summary": summary, **extra})

        if "run" not in last or last["run"][0] != run_status:
            add("run", "run", run_status, f"Analysis {run['state']}.")
        for n in NODES:
            status, summary = cur[n["id"]]
            if last.get(n["id"]) == (status, summary):
                continue
            tool = tool_label(n["id"], run)
            add(n["id"], "status", status, summary or "", tool=tool)
            if status == "running" and tool:
                add(n["id"], "tool_call", status, f"Called {tool}.", tool=tool)
            if status in ("completed", "completed_with_warnings"):
                following = [m["label"] for m in NODES if n["id"] in m["deps"] and cur[m["id"]][0] not in ("unavailable", "skipped")]
                add(n["id"], "handoff", status, ("Output passed to: " + ", ".join(following) + ".") if following else "Output stored with the run.",
                    to=[m["id"] for m in NODES if n["id"] in m["deps"]])
        if new:
            with _path(run_dir).open("a") as f:
                for e in new:
                    f.write(json.dumps(e) + "\n")


def log(run_dir: Path, node: str, status: str, summary: str, tool: str | None = None) -> None:
    """Append an event written by an AI agent. Marked origin=agent so the status it records is kept by later syncs."""
    with LOCK:
        events = read_events(run_dir)
        run_id = run_dir.name
        seq = events[-1]["seq"] if events else 0
        rows = [("status", status, summary)] + ([("tool_call", status, f"Called {tool}.")] if status == "running" and tool else [])
        with _path(run_dir).open("a") as f:
            for type_, st, sm in rows:
                seq += 1
                f.write(json.dumps({"seq": seq, "id": f"{run_id}:{seq}", "run_id": run_id, "node": node, "type": type_, "ts": now(), "status": st,
                                    "summary": sm, "tool": tool, "origin": "agent"}) + "\n")


def tool_label(node_id: str, run: dict) -> str | None:
    if node_id == "alignment":
        return (run.get("alignment") or {}).get("tool") or "ANTsPy rigid registration"
    if node_id == "anatomical_analysis":
        t = run.get("segmentation_tool")
        return f"{t['tool']} {t['version']} (imported)" if t else "segmentation import"
    if node_id in ("pair_validation", "technical_checks"):
        return "NeuroTwin scan checks"
    if node_id in ("quality_review", "longitudinal_comparison", "findings_review"):
        return "NeuroTwin rules (no model)"
    if node_id == "report":
        return "deterministic template (no model)"
    return None


def _inputs(node_id: str, run: dict) -> list[str]:
    e, l = f"earlier scan {run['earlier']}", f"later scan {run['later']}"
    return {"pair_validation": [e, l], "technical_checks": [e, l], "alignment": [e, l],
            "quality_review": ["alignment result", "technical scan checks"],
            "anatomical_analysis": ["segmentation files for both scans", "alignment transform"],
            "longitudinal_comparison": ["earlier and later segmentations"], "findings_review": ["regional measurements"],
            "report": ["regional measurements", "findings review", "quality review", "scan limitations"],
            "clinician_review": ["draft report", "regional measurements"]}.get(node_id, [])


def _outputs(node_id: str, run: dict, status: str) -> list[dict]:
    if status not in ("completed", "completed_with_warnings", "awaiting_review"):
        return []
    a = run.get("alignment")
    if node_id == "pair_validation" and run["validation"].get("interval"):
        iv = run["validation"]["interval"]
        return [{"label": f"Interval {iv['months']} months", "target": None}]
    if node_id == "alignment" and a:
        return [{"label": f"Aligned later scan (similarity {a['correlation_before']} to {a['correlation_after']}; {a['rotation_deg']} degrees, {a['shift_mm_voxel_frame']} mm)", "target": "viewer"}]
    if node_id == "anatomical_analysis" and run.get("segmentation_tool"):
        return [{"label": "Segmentation layers on both scans", "target": "viewer"}]
    if node_id == "longitudinal_comparison" and run.get("measurements"):
        return [{"label": f"Regional volume table ({len(run['measurements']['regions'])} regions)", "target": "measurements"}]
    if node_id == "findings_review" and run.get("review"):
        return [{"label": "Findings review", "target": "review"}]
    if node_id == "report" and run.get("report"):
        return [{"label": "Draft report", "target": "report"}]
    if node_id == "clinician_review":
        return [{"label": "Draft report awaiting review", "target": "report"}]
    return []


def _times(events: list[dict]) -> dict:
    t: dict = {}
    for e in events:
        if e["type"] != "status":
            continue
        d = t.setdefault(e["node"], {"started_at": None, "ended_at": None})
        if e["status"] == "running" and d["started_at"] is None:
            d["started_at"] = e["ts"]
        if e["status"] in TERMINAL:
            d["ended_at"] = e["ts"]
            d["started_at"] = d["started_at"] or e["ts"]
        elif d["ended_at"]:
            d["ended_at"] = None
    for d in t.values():
        if d["started_at"] and d["ended_at"]:
            d["duration_ms"] = int((datetime.fromisoformat(d["ended_at"]) - datetime.fromisoformat(d["started_at"])).total_seconds() * 1000)
        else:
            d["duration_ms"] = None
    return t


def _node_view(n: dict, status: str, summary: str | None, run: dict | None, times: dict) -> dict:
    t = times.get(n["id"], {})
    return {"id": n["id"], "label": n["label"], "kind": n["kind"], "role": n["role"], "deps": n["deps"], "implemented": n.get("implemented", True),
            "status": status, "summary": summary, "tool": tool_label(n["id"], run) if run else None,
            "inputs": _inputs(n["id"], run) if run else [], "outputs": _outputs(n["id"], run, status) if run else [],
            "warnings": [summary] if summary and status in ("completed_with_warnings", "failed", "blocked", "cancelled") else [],
            "started_at": t.get("started_at"), "ended_at": t.get("ended_at"), "duration_ms": t.get("duration_ms")}


def activity(run: dict, run_dir: Path, after: int = 0) -> dict:
    """Everything the Agent Activity panel shows for one run: nodes with status, new events since ``after``, and live/historical."""
    all_events = read_events(run_dir)
    has_events = bool(all_events)
    times = _times(all_events)
    step_state = {s["key"]: s["state"] for s in run["steps"]}
    cur = _current(run, step_state, run_dir)
    live = run["state"] in BUSY
    return {"run_id": run["run_id"], "state": run["state"], "parent_run_id": run.get("parent_run_id"), "live": live,
            "historical": not live, "has_events": has_events, "cancel_supported": live,
            "note": None if has_events else "No execution events were recorded for this run: it was saved before event recording existed. Only its stored final state is shown.",
            "nodes": [_node_view(n, *cur[n["id"]], run, times) for n in NODES],
            "events": [e for e in all_events if e["seq"] > after], "last_seq": all_events[-1]["seq"] if all_events else 0,
            "started_at": all_events[0]["ts"] if all_events else None}


def workflow(alignment_available: bool, alignment_needs: str | None) -> dict:
    """The graph before any run: what is built and what this server can run right now. Nothing here has executed."""
    nodes = []
    for n in NODES:
        if n.get("implemented") is False:
            status, summary = "unavailable", n["unavailable"]
        elif n.get("ai_node"):
            from . import agent_runtime as R
            status, summary = ("unavailable", "No model provider is configured on this server.") if R.mode() == "off" else ("waiting", "Runs on request after an analysis.")
        elif n["id"] == "alignment" and not alignment_available:
            status, summary = "unavailable", f"Needs: {alignment_needs}. Saved analyses can still be opened."
        else:
            status, summary = "waiting", "Waits for an analysis to start."
        nodes.append(_node_view(n, status, summary, None, {}))
    return {"run_id": None, "state": "idle", "live": False, "historical": False, "has_events": False, "cancel_supported": False, "note": None,
            "nodes": nodes, "events": [], "last_seq": 0, "started_at": None}
