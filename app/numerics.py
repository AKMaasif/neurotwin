"""Research-only state-space estimator. Parameters are illustrative, not clinically calibrated."""

import numpy as np


def estimate(observations):
    valid = [
        o for o in observations if o["quality"] == "usable" and o["value"] is not None
    ]
    if len(valid) < 3:
        return {
            "status": "insufficient_history",
            "estimate": None,
            "trend": None,
            "interval": None,
            "rci": None,
            "clinical_use": False,
            "model_version": "research-linear-0.1",
        }
    if len({(o["protocol"], o["mode"]) for o in valid}) != 1:
        return {
            "status": "incompatible_protocol",
            "estimate": None,
            "trend": None,
            "interval": None,
            "rci": None,
            "clinical_use": False,
        }
    valid = sorted(valid, key=lambda x: x["time_days"])
    if len({o["time_days"] for o in valid}) != len(valid):
        return {
            "status": "invalid_timestamps",
            "estimate": None,
            "trend": None,
            "interval": None,
            "rci": None,
            "clinical_use": False,
        }
    x = np.array([valid[0]["value"], 0.0])
    p = np.diag([1.0, 1.0])
    baseline = float(x[0])
    p0 = float(p[0, 0])
    cross = p.copy()
    last = valid[0]["time_days"]
    for o in valid[1:]:
        dt = (o["time_days"] - last) / 365.25
        f = np.array([[1, dt], [0, 1]])
        q = 0.1 * np.array([[dt**3 / 3, dt**2 / 2], [dt**2 / 2, dt]])
        p = f @ p @ f.T + q
        x = f @ x
        cross = f @ cross
        h = np.array([[1.0, 0.0]])
        r = np.array([[0.25]])
        k = np.linalg.solve(h @ p @ h.T + r, h @ p).T
        x = x + (k @ (np.array([o["value"]]) - h @ x))
        a = np.eye(2) - k @ h
        p = a @ p @ a.T + k @ r @ k.T
        cross = a @ cross
        last = o["time_days"]
    variance = float(p[0, 0] + p0 - 2 * cross[0, 0])
    rci = (float(x[0]) - baseline) / np.sqrt(variance) if variance > 1e-10 else None
    return {
        "status": "estimated_for_research",
        "estimate": float(x[0]),
        "trend": float(x[1]),
        "interval": [
            float(x[0] - 1.96 * np.sqrt(p[0, 0])),
            float(x[0] + 1.96 * np.sqrt(p[0, 0])),
        ],
        "rci": float(rci) if rci is not None else None,
        "covariance": p.tolist(),
        "clinical_use": False,
        "model_version": "research-linear-0.1",
        "calibration": "illustrative parameters; not trained or clinically validated",
    }
