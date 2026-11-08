"""SATURN-derived research adaptation. No clinical norms or diagnostic cutoffs.

Source: Bissig et al., SATURN 0.4.0 English, Dryad/Zenodo CC0 deposit.
The responsive controls, text prompts, location question and interruption policy
are adaptations, not an implementation validated by the original study.
"""

import datetime as dt
from zoneinfo import ZoneInfo

PROTOCOL = {
    "id": "saturn-derived-research",
    "version": "1.0",
    "name": "SATURN-derived research activities",
    "source_version": "SATURN 0.4.0 English (2020)",
    "source": "https://doi.org/10.5061/dryad.02v6wwpzr",
    "license": "CC0-1.0",
    "clinical_use": False,
    "clinical_approval": "not_obtained",
    "language": "en",
    "maximum": 30,
    "time_limit_seconds": 900,
    "consent_version": "assessment-research-1",
    "consent_text": (
        "These optional English research activities test this software using a fictional patient. "
        "Your answers, action timings, device category, assistance and interruptions are stored "
        "for clinician review. This adapted test is not validated for this app, phones or Gulf "
        "populations and does not diagnose dementia. No camera or microphone is recorded. "
        "You may skip an activity, stop or withdraw. Withdrawal stops capture and hides results "
        "from use; existing records and security audit history are retained, not deleted. "
        "Do not use the AI companion, other people or reference material to answer. "
        "Only take part if you understand the instructions and can comfortably read English."
    ),
}

WORDS = [
    "ACID",
    "ACTOR",
    "APPLE",
    "APRON",
    "ALBUM",
    "ANT",
    "ARCH",
    "ARM",
    "ASH",
    "ATTIC",
    "AUTO",
    "BANANA",
    "BELT",
    "BIKE",
    "BLUE",
    "BOAT",
    "CAKE",
    "CAR",
    "CHURCH",
    "COFFEE",
    "COW",
    "DIME",
    "DOG",
    "DOLLAR",
    "DRESS",
    "EAR",
    "EAGLE",
    "EGG",
    "FABRIC",
    "FARM",
    "FLAG",
    "FUSE",
    "GARAGE",
    "GOLD",
    "GREEN",
    "HANDLE",
    "HAT",
    "HONEY",
    "HOUSE",
    "HUT",
    "JAZZ",
    "KNOT",
    "LIE",
    "LEMON",
    "LOG",
    "MAN",
    "MAPLE",
    "MILK",
    "MUG",
    "NICKEL",
    "NOSE",
    "NUT",
    "OAK",
    "OIL",
    "ORANGE",
    "OVEN",
    "OWL",
    "PEAR",
    "PEN",
    "PENCIL",
    "PIG",
    "QUIZ",
    "RED",
    "RIB",
    "ROOM",
    "ROSE",
    "SAIL",
    "SHED",
    "SHOE",
    "SISTER",
    "SKY",
    "STAPLE",
    "STAR",
    "STORE",
    "TABLE",
    "TEA",
    "TEEN",
    "TENNIS",
    "THROAT",
    "THUMB",
    "TICKET",
    "TIE",
    "TOE",
    "TONGUE",
    "TOOTH",
    "TOWN",
    "TRAIN",
    "TREE",
    "TRUCK",
    "TUB",
    "URGE",
    "VAN",
    "WAVE",
    "WEB",
    "WHITE",
    "WOLF",
    "WOMAN",
    "WOOD",
    "YARN",
    "YOGA",
]
STROOP_WORDS = "hand book table green red blue red blue green red blue red green blue green".split()
STROOP_COLORS = (
    "blue red green blue green red blue green red green red blue red green blue".split()
)
PHRASES = [
    "WAVE GOODBYE",
    "RAISE YOUR ARMS",
    "CLOSE YOUR EYES",
    "GIVE A SALUTE",
    "WIGGLE YOUR TOES",
    "CLAP YOUR HANDS",
]


def item(key, prompt, maximum=0, kind="choice", options=None, answer=None, **extra):
    return dict(
        id=key,
        prompt=prompt,
        maximum=maximum,
        kind=kind,
        options=options or [],
        answer=answer,
        **extra,
    )


def steps(reference):
    """Freeze orientation reference at consent in the assigned IANA timezone."""
    months = "January February March April May June July August September October November December".split()
    days = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
    return [
        item(
            "reading",
            "Read this phrase: CLOSE YOUR EYES. Then choose Continue. You do not need to act it out.",
            kind="ack",
        ),
        item(
            "attention_j",
            "Pick the word that starts with J.",
            2,
            options="ACID KNOT DIME OVEN FARM SHOE GOLD TREE JAZZ WOLF".split(),
            answer=["JAZZ"],
            error_sensitive=True,
        ),
        item(
            "attention_fruit",
            "Pick the two fruit words.",
            2,
            options=["BANANA", "CHURCH", "ORANGE", "STAPLE"],
            answer=["BANANA", "ORANGE"],
            count=2,
            error_sensitive=True,
        ),
        item(
            "attention_number",
            "Enter the number 1239.",
            2,
            kind="number",
            answer=["1239"],
            error_sensitive=True,
        ),
        item(
            "learning",
            "Remember these five words. Each appears for two seconds with a one-second gap. They will not be shown again.",
            kind="learning",
            words=["APPLE", "CAR", "HOUSE", "PEN", "TIE"],
        ),
        item(
            "memory_phrase",
            "Earlier, what phrase did you first read?",
            1,
            options=PHRASES,
            answer=["CLOSE YOUR EYES"],
        ),
        item(
            "memory_j",
            "Earlier, which J word did you choose?",
            1,
            options="ACID KNOT DIME OVEN FARM SHOE GOLD TREE JAZZ WOLF".split(),
            answer=["JAZZ"],
        ),
        item(
            "memory_number",
            "What number did you enter earlier?",
            1,
            kind="number",
            answer=["1239"],
        ),
        item(
            "month", "What month is it?", 1, options=months, answer=[reference["month"]]
        ),
        item("year", "What year is it?", 1, kind="number", answer=[reference["year"]]),
        item(
            "weekday",
            "What day of the week is it?",
            1,
            options=days,
            answer=[reference["weekday"]],
        ),
        item(
            "location",
            "Which state or emirate are you in?",
            1,
            kind="text",
            answer=[reference["location"]],
        ),
        item(
            "recall",
            "Earlier, you memorized five words. Pick those five words from this list.",
            5,
            options=WORDS,
            answer=["APPLE", "CAR", "HOUSE", "PEN", "TIE"],
            count=5,
        ),
        item(
            "math_spent",
            "You go to the store with exactly $100. You buy a dozen apples for $7 and a tricycle for $60. How much did you spend?",
            1,
            kind="number",
            answer=["67"],
        ),
        item(
            "math_left",
            "After that purchase, how much do you have left?",
            2,
            kind="number",
            answer=["33"],
        ),
        *[
            item(
                f"visual_{i}",
                "Which two small drawings make the large drawing? Number the choices left to right, top row then bottom row.",
                1,
                options=["1", "2", "3", "4", "5", "6"],
                answer=answer,
                count=2,
                image=f"/dashboard/assessment-assets/_drawings_0{i}.png",
            )
            for i, answer in enumerate(
                [["1", "5"], ["2", "6"], ["3", "6"], ["3", "4"]], 1
            )
        ],
        item(
            "stroop",
            "Choose the INK COLOR of each word, not what the word says. The first three are practice. If needed, try another color to continue.",
            3,
            kind="stroop",
            trials=[dict(word=w, color=c) for w, c in zip(STROOP_WORDS, STROOP_COLORS)],
        ),
        item(
            "trails_a",
            "Select the dots in number order, starting at 1 and ending at 5. Your first sequence is saved; corrections are not offered in this adaptation.",
            1,
            kind="trail",
            options=["2", "4", "1", "3", "5"],
            answer=["1", "2", "3", "4", "5"],
        ),
        item(
            "trails_b",
            "Alternate numbers and letters: 1, A, then the next number and letter. Continue to D. Your first sequence is saved.",
            1,
            kind="trail",
            options=["4", "D", "A", "1", "B", "2", "C", "3"],
            answer=["1", "A", "2", "B", "3", "C", "4", "D"],
        ),
    ]


def orientation(timezone, location, at):
    local = dt.datetime.fromisoformat(at).astimezone(ZoneInfo(timezone))
    return dict(
        timezone=timezone,
        location=location.strip(),
        month=local.strftime("%B"),
        year=str(local.year),
        weekday=local.strftime("%A"),
        at=at,
    )


def public_step(step):
    return {
        k: v
        for k, v in step.items()
        if k not in {"answer", "maximum", "error_sensitive"}
    }


def validate_response(step, values, attempts):
    """Reject malformed evidence, not incorrect answers; empty means explicit skip."""
    if not values:
        if attempts:
            raise ValueError("A skipped activity cannot contain answer attempts")
        return
    kind = step["kind"]
    if kind in {"ack", "learning"}:
        if values != ["done"] or attempts:
            raise ValueError("Activity acknowledgement required")
    elif kind == "stroop":
        if values != ["done"] or len(attempts) != 15:
            raise ValueError("All 15 color trials require evidence")
        for trial, selected in zip(step["trials"], attempts):
            if (
                not selected
                or selected[-1] != trial["color"]
                or any(c not in {"red", "green", "blue"} for c in selected)
            ):
                raise ValueError("Invalid color-trial evidence")
    elif kind == "trail":
        if (
            len(values) != len(step["options"])
            or set(values) != set(step["options"])
            or attempts
        ):
            raise ValueError("Select every trail dot once")
    elif kind in {"number", "text"}:
        if len(values) != 1 or not values[0].strip() or attempts:
            raise ValueError("One answer is required")
        if kind == "number" and (not values[0].isascii() or not values[0].isdigit()):
            raise ValueError("Use whole-number digits")
    elif (
        len(values) != step.get("count", 1)
        or len(set(values)) != len(values)
        or any(v not in step["options"] for v in values)
        or attempts
    ):
        raise ValueError("Select the required number of available choices")


def score_item(step, response):
    if not response["values"]:
        return None
    values = response["values"]
    if step["kind"] == "stroop":
        errors = sum(
            sum(c != t["color"] for c in selected)
            for t, selected in zip(step["trials"][3:], response["attempts"][3:])
        )
        return max(0, 3 - errors)
    expected = step["answer"]
    if step["id"] == "recall":
        return len(set(values) & set(expected))
    if step["kind"] == "trail":
        return step["maximum"] if values == expected else 0
    correct = {v.strip().casefold() for v in values} == {v.casefold() for v in expected}
    if step.get("error_sensitive") and response.get("corrected"):
        correct = False
    return step["maximum"] if correct else 0


def score_session(payload):
    responses = {r["step_id"]: r for r in payload["responses"]}
    items = []
    for step in payload["steps"]:
        if step["maximum"]:
            response = responses.get(step["id"])
            items.append(
                dict(
                    id=step["id"],
                    maximum=step["maximum"],
                    points=score_item(step, response) if response else None,
                )
            )
    complete = all(i["points"] is not None for i in items)
    return dict(
        items=items,
        maximum=30,
        total=sum(i["points"] for i in items) if complete else None,
        complete=complete,
        interpretation="Unvalidated adaptation; clinician review required. No diagnostic cutoffs.",
    )
