"""Test–retest reliability for an activity measure: ICC, SEM, minimal detectable change and Bland–Altman agreement.

Why it is here: the change engine shows a reliable change index (RCI) that needs a measurement error (SEM). Until a
test–retest study measures one, change.RELIABILITY holds an assumed figure marked provisional. This module is the code
that will replace it: it takes repeated measurements (from a pilot database, or from simulation) and returns the
figures with their 95% confidence intervals. It does not change any setting by itself; a statistician and a clinician
decide whether a measured figure is good enough to use (docs/RELIABILITY_STUDY.md).

Definitions (Shrout & Fleiss 1979; McGraw & Wong 1996; Weir 2005; Koo & Li 2016):
- scores: n people (rows) × k sessions (columns), complete rows only.
- ICC(2,1): two-way random effects, absolute agreement, single measurement. Counts systematic shifts between sessions
  (practice, device) as error. This is the figure for "is a retest the same as the first test?".
- ICC(3,1): two-way mixed effects, consistency. Ignores a shift shared by everyone. Reported beside ICC(2,1) so a
  practice effect shows up as the gap between them.
- SEM = SD × √(1 − ICC), with SD the standard deviation of all scores; also √MSE, the within-person error.
- MDC95 = 1.96 × √2 × SEM: the smallest change between two single sessions larger than measurement error, 95% of the time.
- Bland–Altman (k = 2): mean difference (bias) and 95% limits of agreement.

Standard library only (no scipy): the F quantile comes from the regularised incomplete beta function.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import timedelta

Z95 = 1.959963984540054


# ---------- F distribution (for the ICC confidence intervals) ----------

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def f_cdf(x: float, d1: float, d2: float) -> float:
    return 0.0 if x <= 0 else betainc(d1 / 2, d2 / 2, d1 * x / (d1 * x + d2))


def f_ppf(p: float, d1: float, d2: float) -> float:
    """Quantile of the F distribution, by bisection on the CDF."""
    lo, hi = 0.0, 1.0
    while f_cdf(hi, d1, d2) < p:
        hi *= 2
        if hi > 1e12:
            return math.inf
    for _ in range(200):
        mid = (lo + hi) / 2
        if f_cdf(mid, d1, d2) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12 * max(1.0, hi):
            break
    return (lo + hi) / 2


# ---------- ICC, SEM, MDC ----------

@dataclass
class ReliabilityResult:
    n: int
    k: int
    icc_a: float                     # ICC(2,1), absolute agreement
    icc_a_ci: tuple[float, float]
    icc_c: float                     # ICC(3,1), consistency
    icc_c_ci: tuple[float, float]
    sd: float                        # SD of all scores
    sem: float                       # SD × √(1 − ICC(2,1))
    sem_within: float                # √MSE
    mdc95: float                     # 1.96 × √2 × SEM
    session_means: list[float]
    bias: float | None = None        # Bland–Altman, k = 2: mean of (session 2 − session 1)
    loa: tuple[float, float] | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        return {key: (round(v, 4) if isinstance(v, float) else [round(x, 4) for x in v] if isinstance(v, (list, tuple)) else v)
                for key, v in d.items()}


def icc(scores: list[list[float]], level: float = 0.95) -> ReliabilityResult:
    n = len(scores)
    if n < 3:
        raise ValueError("Need at least 3 people.")
    k = len(scores[0])
    if k < 2 or any(len(r) != k for r in scores):
        raise ValueError("Every person needs the same number (at least 2) of sessions.")
    grand = sum(map(sum, scores)) / (n * k)
    row_m = [sum(r) / k for r in scores]
    col_m = [sum(r[j] for r in scores) / n for j in range(k)]
    ss_total = sum((x - grand) ** 2 for r in scores for x in r)
    ss_r = k * sum((m - grand) ** 2 for m in row_m)
    ss_c = n * sum((m - grand) ** 2 for m in col_m)
    ss_e = ss_total - ss_r - ss_c
    df_r, df_c, df_e = n - 1, k - 1, (n - 1) * (k - 1)
    msr, msc, mse = ss_r / df_r, ss_c / df_c, max(ss_e / df_e, 1e-12)
    a = 1 - level

    icc_c = (msr - mse) / (msr + (k - 1) * mse)
    f_obs = msr / mse
    fl, fu = f_obs / f_ppf(1 - a / 2, df_r, df_e), f_obs * f_ppf(1 - a / 2, df_e, df_r)
    icc_c_ci = ((fl - 1) / (fl + k - 1), (fu - 1) / (fu + k - 1))

    icc_a = (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)
    # McGraw & Wong (1996) case 2A, Satterthwaite degrees of freedom
    if 0 < icc_a < 1:
        aa = k * icc_a / (n * (1 - icc_a))
        bb = 1 + k * icc_a * (n - 1) / (n * (1 - icc_a))
        v = (aa * msc + bb * mse) ** 2 / ((aa * msc) ** 2 / df_c + (bb * mse) ** 2 / df_e)
        fs, fs2 = f_ppf(1 - a / 2, df_r, v), f_ppf(1 - a / 2, v, df_r)
        lo = n * (msr - fs * mse) / (fs * (k * msc + (k * n - k - n) * mse) + n * msr)
        hi = n * (fs2 * msr - mse) / (k * msc + (k * n - k - n) * mse + n * fs2 * msr)
        icc_a_ci = (lo, hi)
    else:
        icc_a_ci = (math.nan, math.nan)

    sd = math.sqrt(ss_total / (n * k - 1))
    sem = sd * math.sqrt(max(0.0, 1 - icc_a))
    out = ReliabilityResult(n, k, icc_a, icc_a_ci, icc_c, icc_c_ci, sd, sem, math.sqrt(mse), Z95 * math.sqrt(2) * sem, col_m)
    if k == 2:
        diffs = [r[1] - r[0] for r in scores]
        bias = sum(diffs) / n
        sdd = math.sqrt(sum((d - bias) ** 2 for d in diffs) / (n - 1))
        out.bias, out.loa = bias, (bias - Z95 * sdd, bias + Z95 * sdd)
    return out


def sample_size(rho1: float = 0.8, rho0: float = 0.6, k: int = 2, alpha: float = 0.05, power: float = 0.8) -> int:
    """People needed to show ICC > rho0 when it is really rho1 (Walter, Eliasziw & Donner 1998; one-sided alpha)."""
    za = _z(1 - alpha)
    zb = _z(power)
    c0 = (1 + k * rho0 / (1 - rho0)) / (1 + k * rho1 / (1 - rho1))
    return math.ceil(1 + 2 * (za + zb) ** 2 * k / (math.log(c0) ** 2 * (k - 1)))


def _z(p: float) -> float:
    """Normal quantile (Acklam's rational approximation, error < 1e-9)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    lo_p = 0.02425
    if p < lo_p:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - lo_p:
        return -_z(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ---------- pairs from a database (pilot data) ----------

def retest_pairs(db, protocol_code: str = "reaction_time", measure: str = "rt_median_ms", min_gap_days: float = 1,
                 max_gap_days: float = 14, practice: int | None = None, exclude_synthetic: bool = True) -> list[dict]:
    """One test–retest pair per person: the first two usable, current records after the practice sessions, between
    min_gap_days and max_gap_days apart. People without such a pair are left out (and counted by the caller)."""
    from sqlalchemy import select
    from . import change
    from .models import Evidence
    q = select(Evidence).where(Evidence.protocol_code == protocol_code, Evidence.measure == measure)
    rows = list(db.scalars(q))
    by: dict[tuple, list] = {}
    for e in rows:
        if exclude_synthetic and (e.producer_id or "").startswith("synthetic-history"):
            continue
        by.setdefault((e.participant_id, e.protocol_version), []).append(e)
    out = []
    for (pid, version), recs in sorted(by.items()):
        done = sorted((e for e in recs if e.status in ("current", "withdrawn")), key=lambda e: (e.recorded_at, e.id))
        skip = {e.id for e in done[:change.practice_count(recs[0].kind, practice)]}
        ok = [e for e in done if e.id not in skip and e.status == "current" and e.quality == "usable" and e.value_num is not None]
        for i, first in enumerate(ok):
            nxt = next((e for e in ok[i + 1:] if timedelta(days=min_gap_days) <= e.recorded_at - first.recorded_at <= timedelta(days=max_gap_days)), None)
            if nxt is not None:
                out.append({"participant_id": pid, "protocol_version": version, "test": float(first.value_num), "retest": float(nxt.value_num),
                            "gap_days": round((nxt.recorded_at - first.recorded_at).total_seconds() / 86400, 2)})
                break
    return out
