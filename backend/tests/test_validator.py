import pytest

from app.validator import Fact, Statement, check, numbers_in

FACTS = [
    Fact.of("E11", "Reaction time (median) 640 ms on 14 Oct 2026, doubtful: the session was interrupted"),
    Fact.of("E28", "Reaction time (median) 590 ms on 4 Nov 2026, usable"),
    Fact.of("C1", "Sleep hours: difference 0.3 h, 95% interval -2.4 to 3.1, within this person's usual variation"),
]


def codes(v):
    return {p.code for p in v.problems}


def test_grounded_draft_passes():
    v = check([Statement("The 14 Oct session was interrupted and its 640 ms result is marked doubtful.", ["E11"]),
               Statement("The latest reaction time was 590 ms.", ["E28"]),
               Statement("Reported sleep differs by 0.3 h, inside the 95% interval of -2.4 to 3.1.", ["C1"])], FACTS)
    assert v.ok and v.problems == []


def test_uncited_statement_fails():
    assert codes(check([Statement("The latest reaction time was 590 ms.")], FACTS)) == {"uncited"}


def test_citation_must_be_a_given_fact():
    assert "unknown_citation" in codes(check([Statement("Reaction time was 590 ms.", ["E99"])], FACTS))


def test_misquoted_number_fails():
    v = check([Statement("The latest reaction time was 509 ms.", ["E28"])], FACTS)
    assert codes(v) == {"unsupported_number"} and "509" in v.problems[0].detail


def test_number_from_a_fact_that_was_not_cited_fails():
    assert "unsupported_number" in codes(check([Statement("Reaction time was 640 ms.", ["E28"])], FACTS))


@pytest.mark.parametrize("text,code", [
    ("The 640 ms result is consistent with dementia.", "clinical_claim"),
    ("This suggests a risk of further decline.", "clinical_claim"),
    ("The 640 ms result is normal for her age.", "normative_claim"),
    ("She should see a neurologist about the 640 ms result.", "treatment_advice"),
    ("Consider adjusting the medication.", "treatment_advice"),
    ("There is nothing to worry about in the 640 ms result.", "reassurance"),
    ("This is not a diagnosis.", "clinical_claim"),
])
def test_clinical_and_advisory_wording_is_refused(text, code):
    assert code in codes(check([Statement(text, ["E11"])], FACTS))


@pytest.mark.parametrize("text,code", [
    ("النتيجة ٦٤٠ تتوافق مع الخرف.", "clinical_claim"),
    ("النتيجة ٦٤٠ طبيعية.", "normative_claim"),
    ("يجب مراجعة الطبيب.", "treatment_advice"),
    ("لا داعي للقلق.", "reassurance"),
])
def test_arabic_wording_is_refused(text, code):
    assert code in codes(check([Statement(text, ["E11"])], FACTS))


def test_arabic_digits_are_read_as_numbers():
    assert numbers_in("٦٤٠ و 7.0 و ٠٫٣") == {"640", "7", "0.3"}
    assert check([Statement("زمن الاستجابة ٦٤٠ ملي ثانية في جلسة انقطعت.", ["E11"])], FACTS).ok


def test_empty_long_and_oversized_drafts_fail():
    assert codes(check([], FACTS)) == {"empty"}
    assert "too_long" in codes(check([Statement("The session was interrupted. " * 20, ["E11"])], FACTS))
    assert "too_many" in codes(check([Statement("The session was interrupted.", ["E11"])] * 13, FACTS))


def test_verdict_lists_every_problem_with_its_statement():
    v = check([Statement("The latest reaction time was 590 ms.", ["E28"]),
               Statement("Probably dementia, 700 ms.", ["E11"])], FACTS)
    assert not v.ok and {p.index for p in v.problems} == {1}
    assert codes(v) == {"unsupported_number", "clinical_claim"}
    assert v.as_dict()["version"] == "output-validator/0.1"
