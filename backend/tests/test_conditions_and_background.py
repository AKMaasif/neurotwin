"""Today's conditions (vision, hearing, sleep, quiet place) and the person's background (education, first language):
recorded as the person said, used only as stated in app/quality.py, shown to the clinician, never used to change a value."""
import pytest

from conftest import consent, run_reaction, sign_in


def rt_record(r):
    return next(e for e in r.json()["evidence"] if e["measure"] == "rt_median_ms")


@pytest.mark.parametrize("conditions,level,reason", [
    ({"see_clearly": False}, "doubtful", "vision_difficulty"),
    ({"quiet_place": False}, "doubtful", "noisy_place"),
    ({"slept_well": False}, "usable", "poor_sleep"),
    ({"hear_clearly": False}, "usable", "hearing_difficulty"),
])
def test_each_difficulty_is_labelled_as_designed(client, yousef, conditions, level, reason):
    consent(client, yousef)
    r = run_reaction(client, yousef, conditions=conditions)
    assert r.status_code == 200, r.text
    rec = rt_record(r)
    assert rec["quality"] == level and reason in rec["quality_reasons"]
    assert rec["value_num"] == 500, "conditions label a value, never change it"


def test_good_conditions_and_unanswered_add_nothing(client, yousef):
    consent(client, yousef)
    for conds in ({"see_clearly": True, "hear_clearly": True, "slept_well": True, "quiet_place": True}, {}):
        rec = rt_record(run_reaction(client, yousef, conditions=conds))
        assert rec["quality"] == "usable" and rec["quality_reasons"] == []


def test_conditions_do_not_raise_to_check_items(client, yousef):
    consent(client, yousef)
    run_reaction(client, yousef, conditions={"see_clearly": False, "quiet_place": False, "slept_well": False})
    assert client.get("/api/participants/demo-yousef/review-items", headers=yousef).json() == []


def test_session_returns_its_conditions(client, yousef):
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "0.1",
                                           "see_clearly": True, "slept_well": False}, headers=yousef).json()
    assert s["conditions"] == {"see_clearly": True, "hear_clearly": None, "slept_well": False, "quiet_place": None}


def test_clinician_report_counts_difficulties(client):
    h = sign_in(client, "dr.layla")
    rep = client.get("/api/participants/demo-fatima/report", headers=h).json()
    assert rep["sessions"]["slept_well"] == 1 and rep["sessions"]["see_clearly"] == 0


def test_background_is_the_persons_to_set_and_the_clinicians_to_read(client):
    me = sign_in(client, "yousef")
    got = client.get("/api/me/background", headers=me).json()
    assert got["education"] == "university" and "postgraduate" in got["options"]["education"]
    r = client.put("/api/me/background", json={"education": "secondary", "first_language": None}, headers=me)
    assert r.status_code == 200 and r.json()["education"] == "secondary" and r.json()["first_language"] is None
    assert client.put("/api/me/background", json={"education": "phd"}, headers=me).status_code == 422
    doc = sign_in(client, "dr.layla")
    fatima = next(p for p in client.get("/api/clinician/participants", headers=doc).json() if p["id"] == "demo-fatima")
    assert fatima["background"] == {"education": "secondary", "first_language": "arabic"}


@pytest.mark.parametrize("who", ["dr.layla", "mariam"])
def test_only_the_person_sets_background(client, who):
    h = sign_in(client, who)
    assert client.put("/api/me/background", json={"education": "primary"}, headers=h).status_code == 404
    assert client.get("/api/me/background", headers=h).status_code == 404


def test_audit_records_the_change_never_the_answer(client):
    me = sign_in(client, "yousef")
    client.put("/api/me/background", json={"education": "primary", "first_language": "english"}, headers=me)
    log = client.get("/api/participants/demo-yousef/audit", headers=me).json()
    row = next(a for a in log if a["action"] == "profile.background")
    assert "primary" not in str(row) and "english" not in str(row)
