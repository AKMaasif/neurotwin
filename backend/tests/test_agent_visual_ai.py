import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

from app import agent_analysis as A
from app import agent_runtime as R
from app import agent_visual as VS
from app import agent_visual_ai as VA
from app import llm
from test_agent_ledger import RUN, region

ON = {"NEUROTWIN_AGENTS_SEND_IMAGES": "1"}


class Fake:
    def __init__(self, provider, text):
        self.provider, self.model, self.text, self.images = provider, f"{provider}-v", text, []

    def complete(self, system, user, json_mode=False, images=None):
        self.images.append(len(images or []))
        return llm.Reply(self.text(user) if callable(self.text) else self.text, self.provider, self.model)


@pytest.fixture
def world(monkeypatch, tmp_path):
    n = 40
    z, y, x = np.mgrid[:n, :n, :n]
    ball = ((x - 20) ** 2 + (y - 20) ** 2 + (z - 20) ** 2) < 14 ** 2
    earlier = np.where(ball, 50.0 + x + y, 0.0)
    later = np.where(((x - 21) ** 2 + (y - 20) ** 2 + (z - 20) ** 2) < 14 ** 2, 50.0 + x + y, 0.0)
    el = np.where(ball, 4, 0)
    ll = np.where(((x - 22) ** 2 + (y - 20) ** 2 + (z - 20) ** 2) < 14 ** 2, 4, 0)
    ll_same = el
    vols = {"earlier": earlier, "later_aligned": later, "later_original": later}
    labs = {"earlier_seg": el, "later_seg_aligned": ll_same}
    monkeypatch.setattr(pytest, "ll_shifted", ll, raising=False)
    monkeypatch.setattr(A, "layer_volume", lambda run, layer: vols.get(layer))
    monkeypatch.setattr(A, "layer_labels", lambda run, layer: labs.get(layer))
    run = json.loads(json.dumps(RUN))
    run["measurements"]["regions"] += [region(60 + i, f"left thing {i}", 100, 120 + 2 * i) for i in range(6)]  # larger changes push F-R53 out of the top five
    run["validation"]["checks"] = {"earlier": {"voxel_mm": [1, 1, 1], "shape": [n, n, n]}}
    d = tmp_path / "r1"; d.mkdir()
    R._cap.update({"day": None, "n": 0})
    return run, d


def good(user):
    return json.dumps({"observations": [
        {"slice": "S1", "x": 0.5, "y": 0.5, "description": "The edge of the central structure sits slightly further right in the later picture.", "region": "F-R4", "cites": ["F-R4"]},
        {"slice": "S1", "x": 0.5, "y": 0.5, "description": "A faint brightness change near the centre.", "region": "F-R53", "cites": ["F-R53"]},
        {"slice": "S1", "x": 0.02, "y": 0.02, "description": "Something in the corner.", "region": "F-R4", "cites": ["F-R4"]}]})


AGREE = lambda user: json.dumps({"checks": [{"index": i, "verdict": "agreed", "reason": "seen"} for i in range(user.count("Observation "))]})  # noqa: E731


def test_key_slices_are_rule_chosen_and_named(world, monkeypatch):
    run, _ = world
    el = A.layer_labels(run, "earlier_seg")
    monkeypatch.setattr(A, "layer_labels", lambda r, layer: el if layer == "earlier_seg" else pytest.ll_shifted)
    s = VS.key_slices(run)
    assert [x["id"] for x in s] == [f"S{i + 1}" for i in range(len(s))] and {x["view"] for x in s} == {"voxel-axis-3", "voxel-axis-2"}
    assert any("largest labelled-boundary" in x["reason"] for x in s)


def test_observation_rules(world):
    run, _ = world
    sl = {"S1": {}}; masks = {"S1": np.pad(np.ones((10, 10), bool), 5)}  # tissue only in the middle of a 20x20 picture
    facts = {"F-R4": 1, "F-R53": 1}; top = {"F-R4"}
    c = lambda **k: VA.check_observation({"slice": "S1", "x": 0.5, "y": 0.5, "description": "The edge moved.", "region": "F-R4", "cites": ["F-R4"], **k}, sl, masks, facts, top)  # noqa: E731
    assert c()["status"] == "supported" and c()["reason"]
    assert c(cites=["F-R53"])["status"] == "unsupported"
    assert c(slice="S9")["reject_code"] == "unknown_slice"
    assert c(x=1.4)["reject_code"] == "no_location" and c(x="a")["reject_code"] == "no_location"
    assert c(x=0.02, y=0.02)["reject_code"] == "no_tissue"
    assert c(description="Looks like Alzheimer's disease.")["reject_code"] == "forbidden_wording"
    assert c(description="It grew by 7 voxels.")["reject_code"] == "added_number"
    assert c(cites=["F-total"])["reject_code"] == "no_measurement" and c(cites=["F-R999"])["reject_code"] == "no_measurement"
    assert c()["drawn"] is False  # drawing is decided after the second reader


def test_happy_path_draws_only_supported_and_logs_images(world):
    run, d = world
    a, b = Fake("gemini", good), Fake("meta", AGREE)
    rec = VA.observe(run, d, a9_client=a, b_client=b, env=ON)
    st = {o["index"]: o["status"] for o in rec["observations"]}
    assert st == {0: "supported", 1: "unsupported", 2: "rejected"}
    assert [o["drawn"] for o in rec["observations"]] == [True, False, False]
    assert rec["observations"][1]["needs_look"] and rec["cross_check"]["status"] == "completed" and "not measured" in rec["note"]
    eg = R.read(d, R.EGRESS)
    assert all(e["images"] >= 2 for e in eg) and eg[0]["image_names"][0] == "S1_earlier.png" and eg[0]["sent_outside"] is True
    assert a.images[0] == eg[0]["images"] and b.images[0] == eg[1]["images"]
    assert VA.load(d)["observer"]["model"] == "gemini-v"


def test_second_reader_disagreement_removes_the_drawing(world):
    run, d = world
    dis = lambda user: json.dumps({"checks": [{"index": 0, "verdict": "disputed", "reason": "no difference"}, {"index": 1, "verdict": "agreed", "reason": ""}]})  # noqa: E731
    rec = VA.observe(run, d, a9_client=Fake("gemini", good), b_client=Fake("meta", dis), env=ON)
    o = rec["observations"][0]
    assert o["status"] == "supported" and o["drawn"] is False and o["needs_look"] and o["cross"]["verdict"] == "disputed"


def test_missing_second_reader_keeps_drawing_but_says_not_cross_checked(world):
    run, d = world
    rec = VA.observe(run, d, a9_client=Fake("gemini", good), b_client=None, env=ON)
    assert rec["cross_check"]["status"] == "unavailable" and rec["observations"][0]["drawn"] is True and "cross" not in rec["observations"][0]


def test_images_stay_home_unless_switched_on(world):
    run, d = world
    a = Fake("gemini", good)
    rec = VA.observe(run, d, a9_client=a, b_client=Fake("meta", AGREE), env={})
    assert rec["observer"]["status"] == "unavailable" and "switched off" in rec["observer"]["reason"] and rec["observations"] == []
    assert a.images == [] and not (d / R.EGRESS).exists()


def test_bad_json_and_failure_give_no_observations(world):
    run, d = world
    rec = VA.observe(run, d, a9_client=Fake("gemini", "no json"), env=ON)
    assert rec["observer"]["status"] == "failed" and rec["observations"] == []


def test_mock_is_scripted_and_stays_home(world, monkeypatch):
    run, d = world
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "mock")
    rec = VA.observe(run, d)
    assert rec["observer"]["scripted"] is True and rec["observations"] and "Scripted" in rec["observations"][0]["description"]
    assert all(e["sent_outside"] is False for e in R.read(d, R.EGRESS))


def test_missing_layers_are_refused(world, monkeypatch):
    run, d = world
    monkeypatch.setattr(A, "layer_volume", lambda r, l: None)
    with pytest.raises(ValueError):
        VA.observe(run, d, env=ON)
