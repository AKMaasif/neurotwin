"""Output validator: the gate every model-written draft must pass before a person sees it.

Deterministic, no model. A draft is a list of statements; each statement must name the facts it rests on. A fact is
something already stored (a record, a session, a change estimate) that the drafter was given, with the numbers it
contains. The validator refuses a draft when any statement:

- cites nothing, or cites a fact the drafter was not given                    (uncited, unknown_citation)
- contains a number that is not in the facts it cites                         (unsupported_number)
- names a diagnosis or condition, predicts, or speaks of risk or decline      (clinical_claim)
- mentions medication, doses or treatment, or tells the reader what to do     (treatment_advice)
- compares the person with other people or calls a result normal or abnormal  (normative_claim)
- reassures ("nothing to worry about")                                        (reassurance)
- claims significance or proof ("significant", "statistically", "confirmed")   (significance_claim)
- is too long, or the draft has too many statements or none                   (too_long, too_many, empty)

Passing means the draft broke none of these rules. It does not mean the draft is right, complete or well worded:
that is the clinician's review, which always follows. The word lists catch plain wording in English and Arabic, not
every paraphrase, and numbers written as words are not checked. How often the validator misses or over-blocks has
not been measured yet (docs/STATUS.md).

A blunt rule on purpose: the listed words are refused even inside a denial ("this is not a diagnosis"). Drafts state
what was recorded; the app adds its own fixed notices around them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

VERSION = "output-validator/0.1"
MAX_STATEMENTS = 12
MAX_CHARS = 400

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_AR_MARKS = re.compile(r"[ً-ْٰـ]")


def numbers_in(text: str) -> set[str]:
    """Numbers as written, in one form: Western digits, no trailing zeros ("7.0" and "٧" both give "7")."""
    out = set()
    for m in _NUMBER.findall(text.translate(_DIGITS)):
        out.add(m.rstrip("0").rstrip(".") if "." in m else m.lstrip("0") or "0")
    return out


@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    numbers: frozenset[str] = frozenset()

    @staticmethod
    def of(fact_id: str, text: str) -> "Fact":
        return Fact(fact_id, text, frozenset(numbers_in(text)))


@dataclass
class Statement:
    text: str
    cites: list[str] = field(default_factory=list)


@dataclass
class Problem:
    index: int          # which statement, from 0; -1 for the draft as a whole
    code: str
    detail: str


@dataclass
class Verdict:
    ok: bool
    problems: list[Problem]
    version: str = VERSION

    def as_dict(self) -> dict:
        return {"ok": self.ok, "version": self.version,
                "problems": [{"index": p.index, "code": p.code, "detail": p.detail} for p in self.problems]}


def _en(*patterns: str) -> list[re.Pattern]:
    return [re.compile(rf"\b(?:{p})\b", re.IGNORECASE) for p in patterns]


RULES: dict[str, dict] = {
    "clinical_claim": {
        "en": _en(r"diagnos\w*", r"dementia", r"alzheimer\w*", r"parkinson\w*", r"mild cognitive impairment", r"MCI",
                  r"impairment", r"impaired", r"disorder", r"disease", r"prognos\w*", r"predict\w*", r"risk",
                  r"deteriorat\w*", r"declin\w*", r"worsen\w*", r"worse", r"symptom\w*"),
        "ar": ["تشخيص", "خرف", "زهايمر", "ضعف ادراكي", "ضعف إدراكي", "اضطراب", "مرض", "تدهور", "تنبؤ", "يتنبأ", "خطر",
               "أعراض", "اعراض"],
    },
    "treatment_advice": {
        "en": _en(r"medicat\w*", r"medicine\w*", r"dos(?:e|es|age)", r"prescri\w*", r"drug\w*", r"treatment\w*",
                  r"therap\w*", r"should", r"must", r"recommend\w*", r"advis\w*"),
        "ar": ["دواء", "أدوية", "ادوية", "جرعة", "علاج", "وصفة", "يجب", "ينبغي", "نوصي", "ننصح"],
    },
    "normative_claim": {
        "en": _en(r"normal\w*", r"abnormal\w*", r"healthy", r"unhealthy", r"average person", r"for (?:his|her|their) age",
                  r"other (?:people|patients|adults)", r"population", r"typical\w*"),
        "ar": ["طبيعي", "غير طبيعي", "سليم", "الاخرين", "الآخرين", "لعمره", "لعمرها", "المعدل العام"],
    },
    "significance_claim": {
        "en": _en(r"signific\w*", r"statistical\w*", r"p-?values?", r"confirmed", r"proves?", r"proven", r"definite\w*"),
        "ar": ["دلالة إحصائية", "ذو دلالة", "ذات دلالة", "مؤكد", "مؤكدة", "ثبت", "يثبت"],
    },
    "reassurance": {
        "en": _en(r"nothing to worry", r"no cause for concern", r"no need to worry", r"reassur\w*", r"rest assured"),
        "ar": ["لا داعي للقلق", "لا يدعو للقلق", "اطمئن", "اطمئني"],
    },
}


def _banned(text: str) -> list[tuple[str, str]]:
    hits = []
    plain_ar = _AR_MARKS.sub("", text)
    for code, rule in RULES.items():
        for pattern in rule["en"]:
            m = pattern.search(text)
            if m:
                hits.append((code, m.group(0)))
                break
        else:
            for term in rule["ar"]:
                if _AR_MARKS.sub("", term) in plain_ar:
                    hits.append((code, term))
                    break
    return hits


def check(statements: list[Statement], facts: list[Fact]) -> Verdict:
    problems: list[Problem] = []
    by_id = {f.id: f for f in facts}
    if not statements:
        problems.append(Problem(-1, "empty", "The draft has no statements."))
    if len(statements) > MAX_STATEMENTS:
        problems.append(Problem(-1, "too_many", f"{len(statements)} statements; at most {MAX_STATEMENTS}."))

    for i, s in enumerate(statements):
        text = (s.text or "").strip()
        if not text:
            problems.append(Problem(i, "empty", "Empty statement."))
            continue
        if len(text) > MAX_CHARS:
            problems.append(Problem(i, "too_long", f"{len(text)} characters; at most {MAX_CHARS}."))
        cited = [by_id[c] for c in s.cites if c in by_id]
        unknown = [c for c in s.cites if c not in by_id]
        if not s.cites:
            problems.append(Problem(i, "uncited", "No fact is cited."))
        for c in unknown:
            problems.append(Problem(i, "unknown_citation", f"{c} is not one of the facts that were given."))
        if s.cites and not unknown:
            allowed = set().union(*(f.numbers for f in cited)) if cited else set()
            extra = sorted(numbers_in(text) - allowed)
            if extra:
                problems.append(Problem(i, "unsupported_number", f"Not in the cited facts: {', '.join(extra)}."))
        for code, word in _banned(text):
            problems.append(Problem(i, code, f"Uses “{word}”."))
    return Verdict(ok=not problems, problems=problems)
