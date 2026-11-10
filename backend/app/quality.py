"""Evidence-quality rules. Plain code, no model.

Each record gets a level (usable, doubtful, unusable) and the reasons for it. The rules never change a value,
never fill a missing one, and never drop a record: a doubtful or unusable record is kept, labelled, and raises a
"To check" item so a person decides what it means.

Reason codes are stable identifiers; the apps translate them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import protocols as P

RULES_VERSION = "quality-rules/0.1"

ORDER = {"usable": 0, "doubtful": 1, "unusable": 2}

# Reasons that raise a "To check" item for a clinician. Others are recorded but need no action.
NEEDS_REVIEW = {
    "unknown_protocol", "unknown_measure", "out_of_range", "too_few_valid_trials", "many_anticipations",
    "interrupted_session", "abandoned_session", "missing_required",
}
# Reasons about the whole session: one "To check" item per session, not one per record in it.
SESSION_LEVEL = {"interrupted_session", "abandoned_session", "missing_required", "unknown_protocol"}


@dataclass
class ObservationIn:
    measure: str
    kind: str
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    missing_reason: str | None = None


@dataclass
class SessionContext:
    status: str               # completed | interrupted | abandoned
    assisted: bool = False
    unwell_today: bool | None = None
    interruptions: int = 0


@dataclass
class Verdict:
    level: str = "usable"
    reasons: list[str] = field(default_factory=list)

    def add(self, level: str, reason: str) -> None:
        if reason not in self.reasons:
            self.reasons.append(reason)
        if ORDER[level] > ORDER[self.level]:
            self.level = level

    @property
    def needs_review(self) -> bool:
        return any(r in NEEDS_REVIEW for r in self.reasons)


class EvidenceRejected(ValueError):
    """The submission is malformed (not merely low quality) and is not stored."""


def check_shape(obs: ObservationIn) -> None:
    """Refuse records that would hide what happened. Low quality is stored; ambiguity is not."""
    has_value = obs.value_num is not None or (obs.value_text is not None and obs.value_text != "")
    if not has_value and not obs.missing_reason:
        raise EvidenceRejected(f"{obs.measure}: no value and no missing_reason. Missing data must say why.")
    if has_value and obs.missing_reason:
        raise EvidenceRejected(f"{obs.measure}: has both a value and a missing_reason.")


def assess_session(protocol: P.Protocol | None, ctx: SessionContext,
                   observations: list[ObservationIn]) -> list[Verdict]:
    verdicts = [Verdict() for _ in observations]
    by_code = {o.measure: o for o in observations}

    for obs, v in zip(observations, verdicts):
        check_shape(obs)

        if protocol is None:
            v.add("unusable", "unknown_protocol")
            continue
        m = protocol.measure(obs.measure)
        if m is None:
            v.add("unusable", "unknown_measure")
            continue
        if obs.kind != m.kind:
            raise EvidenceRejected(f"{obs.measure}: kind {obs.kind!r} does not match protocol kind {m.kind!r}.")

        if obs.missing_reason:
            v.add("unusable", "missing_value")
        elif m.value_type == "number":
            if obs.value_num is None:
                raise EvidenceRejected(f"{obs.measure}: expects a number.")
            if (m.valid_min is not None and obs.value_num < m.valid_min) or \
               (m.valid_max is not None and obs.value_num > m.valid_max):
                v.add("unusable", "out_of_range")

        # Conditions of the session apply to every record in it.
        if ctx.status == "abandoned":
            v.add("unusable", "abandoned_session")
        elif ctx.status == "interrupted" or ctx.interruptions > 0:
            v.add("doubtful", "interrupted_session")
        if ctx.assisted and m.kind == "observed":
            v.add("doubtful", "assisted_session")
        if ctx.unwell_today and m.kind == "observed":
            v.add("doubtful", "participant_unwell")

    if protocol is not None:
        # Required measures that were not submitted at all.
        for m in protocol.measures:
            if m.required and m.code not in by_code and ctx.status == "completed":
                for v in verdicts:
                    v.add("doubtful", "missing_required")
        if "reaction_time_trials" in protocol.rules:
            _reaction_time_trials(by_code, observations, verdicts)

    return verdicts


def _reaction_time_trials(by_code, observations, verdicts) -> None:
    """A median from fewer than 3 valid trials is not used; 2 or more early taps make it doubtful.

    These cut-offs are engineering defaults for the prototype, not clinical thresholds. They are listed in
    docs/STATUS.md as awaiting qualified review.
    """
    valid = by_code.get("valid_trials")
    early = by_code.get("anticipations")
    for obs, v in zip(observations, verdicts):
        if obs.measure != "rt_median_ms":
            continue
        if valid is None or valid.value_num is None or valid.value_num < 3:
            v.add("unusable", "too_few_valid_trials")
        if early is not None and early.value_num is not None and early.value_num >= 2:
            v.add("doubtful", "many_anticipations")
