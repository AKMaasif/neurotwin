"""Run the stage 9 and 10 experiment on the OASIS-2 demographic table and write a plain report.

    python scripts/run_forecast_experiment.py "Demographic Data.xlsx" -o report.json
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import oasis2, research_forecast as R  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("table"); ap.add_argument("-o", "--out", default="report.json")
    ap.add_argument("--repeats", type=int, default=20)
    a = ap.parse_args()
    table = oasis2.load_table(a.table)
    f = R.forecast_cohort(table); s = R.screening_cohort(table)
    report = {
        "stage10_conversion": {**R.evaluate(f, grouped=False, repeats=a.repeats), "failure_cases_candidate": R.failure_cases(f, R.MODELS[R.CANDIDATE], repeats=a.repeats),
                               "median_follow_up_years": sorted(r["follow_up_years"] for r in f["rows"])[len(f["rows"]) // 2]},
        "stage9_screening": R.evaluate(s, grouped=True, repeats=a.repeats),
    }
    report["stage10_conversion"]["negative_control_shuffled_outcomes"] = R.negative_control(f, grouped=False)
    report["stage9_screening"]["negative_control_shuffled_outcomes"] = R.negative_control(s, grouped=True)
    Path(a.out).write_text(json.dumps(report, indent=1))
    for k, v in report.items():
        print(k, {x: v[x] for x in ("n_rows", "n_subjects", "events", "abstained")})
        for m, r in v["models"].items():
            print(f"  {m:22s} AUROC {r['auroc']:.3f} CI [{r['auroc_ci95_subject_bootstrap'][0]:.2f}, {r['auroc_ci95_subject_bootstrap'][1]:.2f}]  Brier skill {r['brier_skill_vs_prevalence']:.3f}")
        print("  verdict", v["verdict"])
        print("  shuffled-outcome control", {m: round(c["mean_auroc"], 2) for m, c in v["negative_control_shuffled_outcomes"].items()})


if __name__ == "__main__":
    main()
