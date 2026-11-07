"""Research pipeline boundary cases; these do not validate a clinical assessment."""

import pytest

from app.numerics import estimate


def reading(day, **updates):
    return {
        "time_days": day,
        "value": 0.1,
        "quality": "usable",
        "protocol": "synthetic-v1",
        "mode": "self",
    } | updates


@pytest.mark.parametrize(
    "observations, expected",
    [
        ([reading(0), reading(7)], "insufficient_history"),
        ([reading(0), reading(7), reading(14, quality="poor")], "insufficient_history"),
        (
            [reading(0), reading(7), reading(14, quality="interrupted")],
            "insufficient_history",
        ),
        (
            [reading(0), reading(7), reading(14, protocol="different-v2")],
            "incompatible_protocol",
        ),
        (
            [reading(0), reading(7), reading(14, mode="assisted")],
            "incompatible_protocol",
        ),
        ([reading(0), reading(0), reading(14)], "invalid_timestamps"),
    ],
    ids=[
        "too_few",
        "poor_quality",
        "interrupted",
        "mixed_protocol",
        "mixed_mode",
        "duplicate_time",
    ],
)
def test_capture_abstains_without_comparable_history(observations, expected):
    result = estimate(observations)
    assert result["status"] == expected
    assert all(result[key] is None for key in ["estimate", "trend", "interval", "rci"])
    assert result["clinical_use"] is False
