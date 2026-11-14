"""The activities a session can run, versioned.

Every activity here is a NeuroTwin prototype. None is a published instrument, none has been reviewed by a
clinician, and no published norms, thresholds or accuracy figures apply to them. `review_status` says so,
and the apps show it. A change to instructions, scoring or valid ranges is a new version: records keep the
version they were made under, and records from different versions are never compared.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Measure:
    code: str
    kind: str                      # observed | self_reported
    unit: str | None
    value_type: str                # number | text
    valid_min: float | None = None
    valid_max: float | None = None
    required: bool = True


@dataclass(frozen=True)
class Protocol:
    code: str
    version: str
    kind: str                      # self_report | performance
    review_status: str
    measures: tuple[Measure, ...]
    rules: tuple[str, ...] = field(default_factory=tuple)   # names of protocol-specific quality rules

    def measure(self, code: str) -> Measure | None:
        return next((m for m in self.measures if m.code == code), None)


PROTOTYPE = "prototype_not_clinically_reviewed"

PROTOCOLS: dict[tuple[str, str], Protocol] = {}


def _add(p: Protocol) -> None:
    PROTOCOLS[(p.code, p.version)] = p


_add(Protocol(
    code="daily_checkin", version="0.1", kind="self_report", review_status=PROTOTYPE,
    measures=(
        Measure("sleep_hours", "self_reported", "h", "number", 0, 16),
        Measure("sleep_quality", "self_reported", "1-5", "number", 1, 5),
        Measure("today_factors", "self_reported", None, "text", required=False),
    ),
))

_add(Protocol(
    code="reaction_time", version="0.1", kind="performance", review_status=PROTOTYPE,
    measures=(
        Measure("rt_median_ms", "observed", "ms", "number", 100, 3000),
        Measure("valid_trials", "observed", "count", "number", 0, 20),
        Measure("anticipations", "observed", "count", "number", 0, 20),
    ),
    rules=("reaction_time_trials",),
))


_add(Protocol(
    code="picture_sequence", version="0.1", kind="performance", review_status=PROTOTYPE,
    measures=(
        Measure("rounds_correct", "observed", "count", "number", 0, 4),
        Measure("rounds_shown", "observed", "count", "number", 0, 4),
        Measure("longest_correct", "observed", "count", "number", 0, 6),
    ),
    rules=("picture_sequence_rounds",),
))

# WHO-5 Well-Being Index (WHO, 1998 version), English wording and 0-5 scoring exactly as published. Raw total 0-25.
# The owner chose to include it. NeuroTwin adds no cut-off, no "meaningful change" label and no interpretation, and no translation:
# an Arabic version is offered only once the owner supplies the official text.
PUBLISHED = "published_instrument_english_unmodified_not_reviewed_here"
_add(Protocol(
    code="who5", version="1998-en", kind="self_report", review_status=PUBLISHED,
    measures=tuple(Measure(f"who5_{i}", "self_reported", "0-5", "number", 0, 5) for i in range(1, 6))
    + (Measure("who5_raw", "self_reported", "0-25", "number", 0, 25),),
    rules=("who5_total",),
))


def get(code: str, version: str) -> Protocol | None:
    return PROTOCOLS.get((code, version))


def as_dict(p: Protocol) -> dict:
    return {
        "code": p.code, "version": p.version, "kind": p.kind, "review_status": p.review_status,
        "measures": [{"code": m.code, "kind": m.kind, "unit": m.unit, "value_type": m.value_type,
                      "valid_min": m.valid_min, "valid_max": m.valid_max, "required": m.required}
                     for m in p.measures],
    }
