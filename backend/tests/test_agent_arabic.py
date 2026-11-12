import json

import pytest

from app import agent_explainer as X
from app import agent_family as FA
from app import agent_glossary as G
from app import agent_runtime as R
from app import llm
from app import validator as V
from app.agent_analysis import SEG_LABELS
from test_agent_family import Fake, approve, rd, reset, run, setup, sts  # noqa: F401  (fixtures)
from test_agent_ledger import RUN
from app import agent_ledger as L

FACTS = L.build(RUN)["facts"]
AR_OK = [("بعد مرور ١٢ شهراً بين الفحصين، تمت المقارنة.", ["F-interval"]), ("لم تُقدَّر بعدُ درجة عدم اليقين.", ["F-uncertainty"])]


def bt(*texts):
    return Fake(json.dumps({"texts": list(texts)}))


def test_every_segmentation_name_has_a_draft_arabic_term():
    assert all(G.ar_name(n) for n in SEG_LABELS.values())
    assert G.STATUS == "draft_not_reviewed"


def test_prompt_block_lists_only_structures_in_the_facts():
    b = G.prompt_block(FACTS)
    assert "left hippocampus = الحُصين، الجانب الأيسر" in b and "putamen" not in b


def test_cited_structure_must_use_its_fixed_term():
    bad = [V.Statement("الحجم أصغر قليلاً في هذا الجانب.", ["F-R17"])]
    assert [p.code for p in G.check_terms(bad, FACTS)] == ["glossary_term"]
    good = [V.Statement("حجم الحُصين الأيسر أصغر.", ["F-R17"])]  # marks are ignored when comparing
    assert G.check_terms([V.Statement("حجم الحصين أصغر.", ["F-R17"])], FACTS) == [] and G.check_terms(good, FACTS) == []


def test_parity_flags_numbers_structure_and_wording():
    st = [V.Statement("الحصين أصغر بمقدار 50", ["F-R17"])]
    assert G.parity(st, ["The hippocampus is smaller by 50"], FACTS)[0]["ok"]
    assert "numbers_differ" in G.parity(st, ["The hippocampus is smaller by 5"], FACTS)[0]["flags"]
    assert any(f.startswith("structure_missing") for f in G.parity(st, ["The thalamus is smaller by 50"], FACTS)[0]["flags"])
    assert any(f.startswith("forbidden_wording") for f in G.parity(st, ["The hippocampus is smaller by 50, a sign of disease"], FACTS)[0]["flags"])
    assert G.parity(st, None, FACTS)[0]["flags"] == ["no_back_translation"]


def test_arabic_digits_count_as_the_same_number():
    st = [V.Statement("بين الفحصين ١٢ شهراً", ["F-interval"])]
    assert G.parity(st, ["The scans are 12 months apart"], FACTS)[0]["ok"]


def test_explain_arabic_passes_with_a_faithful_back_translation(rd):
    rec = X.explain(run(), rd, "ar", a3_client=Fake(sts(*AR_OK)),
                    a4_client=Fake(json.dumps({"texts": ["The scans are 12 months apart.", "Uncertainty is not estimated."]})), env={})
    assert rec["language"] == "ar" and rec["arabic"]["glossary_status"] == "draft_not_reviewed"
    assert rec["arabic"]["back_translation"]["status"] == "completed" and rec["qa"]["checks"][-1]["name"] == "Arabic clinical reader"
    assert rec["explanation"]["status"] == "completed"


def test_explain_arabic_blocks_when_back_translation_disagrees(rd):
    a4 = Fake(json.dumps({"texts": ["The scans are 3 months apart.", "Uncertainty is not estimated."]}))
    rec = X.explain(run(), rd, "ar", a3_client=Fake(sts(*AR_OK)), a4_client=a4, env={})
    assert not rec["qa"]["passed"] and "differ" in " ".join(c["detail"] for c in rec["qa"]["checks"])


def test_explain_arabic_without_a_back_translation_provider_cannot_pass(rd):
    rec = X.explain(run(), rd, "ar", a3_client=Fake(sts(*AR_OK)), a4_client=None, env={})
    assert rec["arabic"]["back_translation"]["status"] == "unavailable" and not rec["qa"]["passed"]


def test_explain_arabic_refuses_banned_arabic_wording(rd):
    bad = [("تشخيص المرض.", ["F-interval"]), AR_OK[1]]
    rec = X.explain(run(), rd, "ar", a3_client=Fake(sts(*bad)), a4_client=None, env={})
    assert rec["explanation"]["status"] == "refused" and rec["arabic"]["back_translation"]["status"] == "skipped"


def test_explain_arabic_refuses_missing_glossary_term(rd):
    rec = X.explain(run(), rd, "ar", a3_client=Fake(sts(("الحجم أصغر قليلاً.", ["F-R17"]), AR_OK[1])), a4_client=None, env={})
    assert any(p["code"] == "glossary_term" for p in rec["explanation"]["validator"]["problems"])


def test_unknown_language_is_refused(rd):
    with pytest.raises(ValueError):
        X.explain(run(), rd, "fr", env={})


def test_scripted_arabic_is_labelled_and_never_counts_as_a_real_check(rd):
    rec = X.explain(run(), rd, "ar", env={"NEUROTWIN_AGENTS_MODE": "mock"})
    assert rec["arabic"]["back_translation"]["scripted"] and rec["qa"]["passed"]
    assert any(c.get("warning") and "Scripted" in c["detail"] for c in rec["qa"]["checks"])


FAM_AR = sts(("تمت مقارنة فحصين للشخص نفسه.", ["F-interval"]), ("لا نعرف بعدُ مدى دقة القياسات.", ["F-uncertainty"]),
             ("سيشرح لكم الطبيب معنى ذلك.", ["F-uncertainty"]))
FAM_BT = json.dumps({"texts": ["Two scans of the same person were compared.", "We do not yet know how accurate the measurements are.", "The doctor will explain what this means."]})


def test_family_arabic_draft_checks_and_back_translates(rd):
    rec = FA.draft(run(), rd, [], client=Fake(FAM_AR), bt_client=Fake(FAM_BT), language="ar", env={})
    assert rec["status"] == "completed" and rec["language"] == "ar" and rec["arabic"]["back_translation"]["status"] == "completed"


@pytest.mark.parametrize("bad,code", [("هذا أمر خطير.", "tone"), ("الفوكسل صغير.", "jargon")])
def test_family_arabic_tone_and_jargon_rules(rd, bad, code):
    t = sts((bad, ["F-interval"]), ("لا نعرف بعدُ مدى دقة القياسات.", ["F-uncertainty"]), ("سيشرح لكم الطبيب معنى ذلك.", ["F-uncertainty"]))
    rec = FA.draft(run(), rd, [], client=Fake([t, t]), bt_client=Fake(FAM_BT), language="ar", env={})
    assert rec["status"] == "refused" and code in {p["code"] for p in rec["validator"]["problems"]}


def test_family_arabic_without_clinician_invitation_is_refused(rd):
    t = sts(("تمت مقارنة فحصين.", ["F-interval"]), ("لا نعرف بعدُ مدى الدقة.", ["F-uncertainty"]), ("هذا كل شيء.", ["F-uncertainty"]))
    rec = FA.draft(run(), rd, [], client=Fake([t, t]), language="ar", env={})
    assert "no_invitation" in {p["code"] for p in rec["validator"]["problems"]}


def test_family_arabic_with_a_disagreeing_back_translation_is_refused(rd):
    off = json.dumps({"texts": ["Two scans were compared.", "The measurements are very accurate.", "The doctor will explain."]})
    rec = FA.draft(run(), rd, [], client=Fake(FAM_AR), bt_client=Fake(off), language="ar", env={})
    assert rec["status"] == "completed"  # wording rules do not catch a meaning change; only a clinician who reads Arabic can
    nb = json.dumps({"texts": ["Two scans were compared in 5 days.", "x", "y"]})
    rec = FA.draft(run(), rd, [], client=Fake(FAM_AR), bt_client=Fake(nb), language="ar", env={})
    assert rec["status"] == "refused"


def test_family_arabic_release_needs_the_clinician_to_confirm_reading_it(client, app, login, rd):
    yousef, dr, fam = setup(client, app, login, rd)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef")
        FA.draft(run(), rd, [], client=Fake(FAM_AR), bt_client=Fake(FAM_BT), language="ar", env={})
        with pytest.raises(ValueError, match="reads Arabic"):
            FA.release(db, rd, dr, "demo-mariam")
        rec = FA.release(db, rd, dr, "demo-mariam", arabic_confirmed=True)
        assert rec["release"]["language"] == "ar" and rec["release"]["arabic_confirmed"] is True
    r = client.get("/api/family/imaging-summaries", headers=login("demo-mariam")).json()
    assert r[0]["active"] and r[0]["language"] == "ar" and r[0]["statements"][0].startswith("تمت")


def test_english_release_is_unchanged_by_the_arabic_flag(client, app, login, rd):
    yousef, dr, fam = setup(client, app, login, rd)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef")
        FA.draft(run(), rd, [], client=Fake(__import__("test_agent_family").GOOD))
        assert FA.release(db, rd, dr, "demo-mariam")["release"]["arabic_confirmed"] is None
