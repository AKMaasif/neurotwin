import json

import pytest

pytest.importorskip("nibabel")
pytest.importorskip("numpy")
pytest.importorskip("PIL")

from app import agent_activity as AC
from app import agent_analysis as A
from test_agent_analysis import clear_cache, data, write_seg  # noqa: F401  (fixtures)


def events_of(run_id):
    return AC.read_events(A.runs_root() / run_id)


def status_of(act, node):
    return next(n for n in act["nodes"] if n["id"] == node)["status"]


def test_new_run_logs_validation_and_waiting_stages(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    ev = events_of(run["run_id"])
    assert [e["seq"] for e in ev] == list(range(1, len(ev) + 1))
    assert len({e["id"] for e in ev}) == len(ev)
    first = {e["node"]: e["status"] for e in ev if e["type"] == "status"}
    assert first["pair_validation"] == "completed" and first["alignment"] == "queued"
    assert first["segmentation_import" if False else "anatomical_analysis"] == "waiting"  # not unavailable while a run is queued


def test_planned_agents_and_missing_brain_extraction_are_never_completed(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    act = AC.activity(run, A.runs_root() / run["run_id"])
    for node in ("evidence_explanation", "report_review_ai", "brain_extraction"):
        n = next(x for x in act["nodes"] if x["id"] == node)
        assert n["status"] == "unavailable" and n["summary"] and not n["implemented"] and not n["outputs"]
    kinds = {n["id"]: n["kind"] for n in act["nodes"]}
    assert kinds["evidence_explanation"] == "ai" and kinds["clinician_review"] == "human" and kinds["alignment"] == "tool"
    assert all(e["status"] != "completed" for e in events_of(run["run_id"]) if e["node"] in ("evidence_explanation", "report_review_ai", "brain_extraction"))


def test_blocked_pair_skips_everything_after(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0002_MR2")
    act = AC.activity(run, A.runs_root() / run["run_id"])
    assert status_of(act, "pair_validation") == "blocked" and status_of(act, "technical_checks") == "skipped"
    assert status_of(act, "alignment") == "skipped" and status_of(act, "clinician_review") == "skipped"


def test_cancel_is_logged_and_downstream_stages_skipped(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    A.cancel(run["run_id"])
    act = AC.activity(A.load_run(run["run_id"]), A.runs_root() / run["run_id"])
    assert act["state"] == "cancelled" and status_of(act, "alignment") == "cancelled" and status_of(act, "report") == "skipped"
    assert any(e["node"] == "run" and e["status"] == "cancelled" for e in events_of(run["run_id"]))
    assert act["live"] is False and act["historical"] is True


def test_sync_is_idempotent(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    n = len(events_of(run["run_id"]))
    AC.sync(A.runs_root() / run["run_id"], A.load_run(run["run_id"]))
    AC.sync(A.runs_root() / run["run_id"], A.load_run(run["run_id"]))
    assert len(events_of(run["run_id"])) == n  # nothing changed, so nothing is repeated


def test_after_cursor_returns_only_newer_events(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    d = A.runs_root() / run["run_id"]
    allev = AC.read_events(d)
    act = AC.activity(run, d, after=allev[2]["seq"])
    assert [e["seq"] for e in act["events"]] == [e["seq"] for e in allev[3:]]
    assert act["last_seq"] == allev[-1]["seq"]


def test_run_without_events_is_labelled_not_reconstructed(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    (A.runs_root() / run["run_id"] / "events.jsonl").unlink()
    act = AC.activity(run, A.runs_root() / run["run_id"])
    assert act["has_events"] is False and act["events"] == [] and "before event recording" in act["note"]


def test_half_written_line_is_ignored(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    d = A.runs_root() / run["run_id"]
    n = len(AC.read_events(d))
    with (d / "events.jsonl").open("a") as f:
        f.write('{"seq": 99, "id"')
    assert len(AC.read_events(d)) == n


def test_complete_run_has_real_times_outputs_and_awaiting_review(data):
    pytest.importorskip("ants")
    write_seg(data, "OAS2_0001_MR1")
    write_seg(data, "OAS2_0001_MR2", labels_shift=-2)
    out = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    d = A.runs_root() / out["run_id"]
    act = AC.activity(out, d)
    assert out["state"] == "complete" and act["historical"]
    assert status_of(act, "report") == "completed" and status_of(act, "clinician_review") == "awaiting_review"
    assert status_of(act, "evidence_explanation") == "unavailable"  # a finished run does not make planned agents real
    node = next(n for n in act["nodes"] if n["id"] == "alignment")
    assert node["started_at"] and node["ended_at"] and node["duration_ms"] >= 0 and node["tool"].startswith("ANTsPy")
    assert node["outputs"][0]["target"] == "viewer"
    assert next(n for n in act["nodes"] if n["id"] == "longitudinal_comparison")["outputs"][0]["target"] == "measurements"
    ev = events_of(out["run_id"])
    order = [e["node"] for e in ev if e["type"] == "status" and e["status"] == "running"]
    assert order.index("alignment") < order.index("anatomical_analysis") < order.index("longitudinal_comparison") < order.index("findings_review") < order.index("report")
    ts = [e["ts"] for e in ev]
    assert ts == sorted(ts)
    assert any(e["type"] == "handoff" and e["node"] == "alignment" for e in ev) and any(e["type"] == "tool_call" for e in ev)
    blob = json.dumps(act).lower()
    assert "prompt" not in blob and "api_key" not in blob


def test_without_segmentation_partial_run_shows_unavailable_not_done(data):
    pytest.importorskip("ants")
    out = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    act = AC.activity(out, A.runs_root() / out["run_id"])
    assert out["state"] == "partial"
    for node in ("anatomical_analysis", "longitudinal_comparison", "findings_review", "report"):
        assert status_of(act, node) == "unavailable"
    assert status_of(act, "clinician_review") == "skipped"
    assert not any(e["status"] == "completed" and e["node"] in ("longitudinal_comparison", "report") for e in events_of(out["run_id"]))


def test_activity_endpoints(client, login, data):
    h = login("demo-dr-layla")
    assert client.get("/api/imaging/agent/workflow").status_code == 401
    assert client.get("/api/imaging/agent/workflow", headers=login("demo-yousef")).status_code == 403
    wf = client.get("/api/imaging/agent/workflow", headers=h).json()
    assert wf["state"] == "idle" and wf["events"] == [] and not any(n["status"] in ("completed", "running") for n in wf["nodes"])
    rid = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"]
    a = client.get(f"/api/imaging/agent/runs/{rid}/activity", headers=h).json()
    assert a["run_id"] == rid and a["events"] and a["last_seq"] == a["events"][-1]["seq"]
    again = client.get(f"/api/imaging/agent/runs/{rid}/activity?after={a['last_seq']}", headers=h).json()
    assert again["events"] == [] and again["last_seq"] == a["last_seq"]
    assert client.get("/api/imaging/agent/runs/zzz/activity", headers=h).status_code == 404
