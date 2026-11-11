"""Stage 9 and 10 research experiment on the OASIS-2 session table.

Everything here follows rules fixed before any result was looked at (docs/IMAGING_WORKFLOW_STAGES_1_10.md):

* Inputs are limited to what exists at the cutoff visit. The dataset's Group label is never an input.
* Evaluation is grouped by subject, so no person is in both the training and the test part.
* Every model is shown next to simple baselines; the experiment reports when the model does not beat them.
* A visit missing a key input abstains and is counted, never filled in silently.
* Output is for research reporting of population-level performance. It is not a statement about an individual.
"""
from __future__ import annotations

import warnings
from collections import defaultdict

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ALL_FEATURES = ["Age", "Female", "EDUC", "MMSE", "eTIV", "nWBV", "ASF"]
KEY_INPUTS = ["Age", "MMSE", "nWBV", "eTIV"]  # without these a visit abstains
MODELS = {
    "prevalence_only": [],
    "age_sex": ["Age", "Female"],
    "mmse_only": ["MMSE"],
    "nwbv_only": ["nWBV"],
    "all_baseline_inputs": ALL_FEATURES,
}
CANDIDATE = "all_baseline_inputs"
FORBIDDEN = {"Group", "CDR", "Visit", "MR Delay", "Subject ID", "MRI ID"}


def _row(r: dict) -> dict:
    out = {k: r.get(k) for k in ("Age", "EDUC", "MMSE", "eTIV", "nWBV", "ASF")}
    out["Female"] = None if r.get("M/F") is None else float(r["M/F"] == "F")
    return out


def _by_subject(table: list[dict]) -> dict[str, list[dict]]:
    subjects = defaultdict(list)
    for r in table:
        subjects[r["Subject ID"]].append(r)
    for v in subjects.values():
        v.sort(key=lambda r: r["MR Delay"])
    return subjects


def forecast_cohort(table: list[dict]) -> dict:
    """Stage 10: subjects whose earliest visit has CDR 0 and who have a later visit. Label: CDR above 0 at any later visit."""
    rows, abstained = [], []
    for sid, visits in _by_subject(table).items():
        first = visits[0]
        if first["CDR"] != 0 or len(visits) < 2:
            continue
        x = _row(first)
        if any(x[k] is None for k in KEY_INPUTS):
            abstained.append({"subject": sid, "missing": [k for k in KEY_INPUTS if x[k] is None]})
            continue
        rows.append({"subject": sid, "x": x, "y": int(any(v["CDR"] > 0 for v in visits[1:])),
                     "follow_up_years": (visits[-1]["MR Delay"] - first["MR Delay"]) / 365.25})
    return {"rows": rows, "abstained": abstained}


def screening_cohort(table: list[dict]) -> dict:
    """Stage 9: every visit, label is CDR above 0 at that same visit. Describes the present, never the future."""
    rows, abstained = [], []
    for sid, visits in _by_subject(table).items():
        for v in visits:
            x = _row(v)
            if any(x[k] is None for k in KEY_INPUTS):
                abstained.append({"subject": sid, "visit": v["MRI ID"], "missing": [k for k in KEY_INPUTS if x[k] is None]})
                continue
            rows.append({"subject": sid, "x": x, "y": int(v["CDR"] > 0)})
    return {"rows": rows, "abstained": abstained}


def _matrix(rows, features):
    return np.array([[r["x"][f] if r["x"][f] is not None else np.nan for f in features] for r in rows], dtype=float)


def _fit_predict(features, Xtr, ytr, Xte):
    if not features:  # prevalence only
        return np.full(len(Xte), ytr.mean())
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(Xtr, ytr)
    return model.predict_proba(Xte)[:, 1]


def out_of_fold(rows, features, *, grouped: bool, folds=5, repeats=20, seed=0):
    """Repeated cross-validation. Returns predictions[repeat, row]. No subject is ever on both sides of a split."""
    y = np.array([r["y"] for r in rows]); groups = np.array([r["subject"] for r in rows])
    X = _matrix(rows, features) if features else np.zeros((len(rows), 1))
    preds = np.full((repeats, len(rows)), np.nan)
    for rep in range(repeats):
        rng = np.random.default_rng(seed + rep)
        if grouped:  # several visits per subject: shuffle the subjects, deal them into folds, keep each subject whole
            subjects = np.unique(groups); rng.shuffle(subjects)
            fold_of = {g: i % folds for i, g in enumerate(subjects)}
            fold = np.array([fold_of[g] for g in groups])
            splitter = ((np.where(fold != k)[0], np.where(fold == k)[0]) for k in range(folds))
        else:  # one row per subject, so stratifying by outcome cannot split a person
            splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed + rep).split(X, y)
        for tr, te in splitter:
            assert not set(groups[tr]) & set(groups[te]), "a subject appears in both train and test"
            preds[rep, te] = _fit_predict(features, X[tr], y[tr], X[te])
    return preds


def calibration(y, p, bins=3):
    order = np.argsort(p); chunks = np.array_split(order, bins)
    table = [{"mean_predicted": float(p[c].mean()), "observed_rate": float(y[c].mean()), "n": int(len(c))} for c in chunks if len(c)]
    z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    slope = intercept = None
    if len(set(y)) == 2 and z.std() > 1e-9:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lr = LogisticRegression(C=1e6, max_iter=1000).fit(z.reshape(-1, 1), y)
        slope, intercept = float(lr.coef_[0][0]), float(lr.intercept_[0])
    return {"bins": table, "slope": slope, "intercept": intercept}


def _boot_auc(y, p, groups, n=2000, seed=1):
    rng = np.random.default_rng(seed); subs = np.unique(groups)
    idx = {s: np.where(groups == s)[0] for s in subs}; vals = []
    for _ in range(n):
        pick = np.concatenate([idx[s] for s in rng.choice(subs, len(subs))])
        if len(set(y[pick])) == 2:
            vals.append(roc_auc_score(y[pick], p[pick]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else [None, None]


def evaluate(cohort: dict, *, grouped: bool, repeats=20, seed=0) -> dict:
    rows = cohort["rows"]
    y = np.array([r["y"] for r in rows]); groups = np.array([r["subject"] for r in rows])
    result = {"n_rows": len(rows), "n_subjects": int(len(set(groups))), "events": int(y.sum()),
              "abstained": len(cohort["abstained"]), "models": {}}
    if len(set(y)) < 2:
        result["note"] = "only one outcome class present; no discrimination can be measured"
        return result
    for name, feats in MODELS.items():
        preds = out_of_fold(rows, feats, grouped=grouped, repeats=repeats, seed=seed)
        p = preds.mean(axis=0)
        aucs = [roc_auc_score(y, preds[r]) for r in range(preds.shape[0])] if feats else [0.5]
        pooled = roc_auc_score(y, p) if feats else 0.5
        briers = [brier_score_loss(y, preds[r]) for r in range(preds.shape[0])]
        result["models"][name] = {
            "features": feats,
            "auroc": float(pooled),  # AUROC of the repeat-averaged out-of-fold predictions; the interval below is for this value
            "auroc_mean_over_repeats": float(np.mean(aucs)),
            "auroc_ci95_subject_bootstrap": _boot_auc(y, p, groups) if feats else [0.5, 0.5],
            "brier_mean_over_repeats": float(np.mean(briers)),
            "calibration": calibration(y, p),
        }
    base = result["models"]["prevalence_only"]["brier_mean_over_repeats"]
    for m in result["models"].values():
        m["brier_skill_vs_prevalence"] = float(1 - m["brier_mean_over_repeats"] / base)
    best_simple = max((k for k in MODELS if k not in (CANDIDATE, "prevalence_only")), key=lambda k: result["models"][k]["auroc"])
    cand = result["models"][CANDIDATE]; simple = result["models"][best_simple]
    result["verdict"] = {
        "best_simple_baseline": best_simple,
        "candidate_auroc": cand["auroc"], "baseline_auroc": simple["auroc"],
        "candidate_beats_best_baseline": bool(cand["auroc"] > simple["auroc"] + 0.02
                                              and cand["brier_mean_over_repeats"] < simple["brier_mean_over_repeats"]),
    }
    return result


def failure_cases(cohort: dict, features, *, top=5, repeats=20, seed=0):
    rows = cohort["rows"]
    preds = out_of_fold(rows, features, grouped=False, repeats=repeats, seed=seed).mean(axis=0)
    y = np.array([r["y"] for r in rows])
    missed = np.argsort(np.where(y == 1, preds, 9))[:top]
    return [{"subject": rows[i]["subject"], "predicted": float(preds[i]), "follow_up_years": rows[i].get("follow_up_years")} for i in missed if y[i] == 1]


def negative_control(cohort: dict, *, grouped: bool, permutations=20, repeats=5, seed=100) -> dict:
    """The same procedure on outcomes shuffled between subjects. With no real signal, cross-validated AUROC is not 0.5:
    leave-out splits push it below 0.5, most for coarse inputs such as MMSE. Real results are read against this."""
    rng = np.random.default_rng(seed); rows = cohort["rows"]
    subjects = sorted({r["subject"] for r in rows})
    out = {name: [] for name in MODELS if name != "prevalence_only"}
    for _ in range(permutations):
        if grouped:  # shuffle each subject's whole outcome pattern between subjects with the same number of visits
            pools = defaultdict(list)
            for sid in subjects:
                pools[sum(r["subject"] == sid for r in rows)].append(sid)
            swap = {}
            for ids in pools.values():
                shuffled = list(ids); rng.shuffle(shuffled); swap.update(dict(zip(ids, shuffled)))
            ys = {sid: [r["y"] for r in rows if r["subject"] == sid] for sid in subjects}
            counter = defaultdict(int); new = []
            for r in rows:
                new.append(ys[swap[r["subject"]]][counter[r["subject"]]]); counter[r["subject"]] += 1
        else:
            new = list(rng.permutation([r["y"] for r in rows]))
        shuffled_rows = [{**r, "y": y} for r, y in zip(rows, new)]
        y = np.array(new)
        if len(set(y)) < 2:
            continue
        for name in out:
            p = out_of_fold(shuffled_rows, MODELS[name], grouped=grouped, repeats=repeats, seed=int(rng.integers(1e6))).mean(axis=0)
            out[name].append(roc_auc_score(y, p))
    return {k: {"mean_auroc": float(np.mean(v)), "p05": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95))} for k, v in out.items() if v}
