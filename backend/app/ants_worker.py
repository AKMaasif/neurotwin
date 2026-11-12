"""ANTsPy jobs run in their own process: ``python -m app.ants_worker register|warp ...``.

ANTs holds Python's global lock for the whole call. Run inside the server it freezes every request (live progress, cancel,
other users) for the length of the registration, and it cannot be stopped. A separate process keeps the server responsive,
and cancelling terminates it. This module imports only numpy and ants, so it starts fast and needs nothing from the web app.
"""
import json
import math
import shutil
import sys
from pathlib import Path


def _angle_deg(matrix) -> float:
    import numpy as np
    r = np.asarray(matrix).reshape(3, 3)
    return float(math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(r) - 1) / 2)))))


def register(work: Path) -> None:
    """Reads fixed.npy, moving.npy and zooms.json from ``work``; writes aligned.npy, transform.mat and result.json there."""
    import ants
    import numpy as np
    d1, d2 = np.load(work / "fixed.npy"), np.load(work / "moving.npy")
    zooms = tuple(json.loads((work / "zooms.json").read_text()))
    fixed = ants.from_numpy(np.ascontiguousarray(d1), spacing=zooms)
    moving = ants.from_numpy(np.ascontiguousarray(d2), spacing=zooms)
    reg = ants.registration(fixed=fixed, moving=moving, type_of_transform="Rigid", aff_metric="mattes")
    aligned = reg["warpedmovout"].numpy().astype("float32")
    mask = d1 > np.percentile(d1, 60)
    before = float(np.corrcoef(d1[mask], d2[mask])[0, 1])
    after = float(np.corrcoef(d1[mask], aligned[mask])[0, 1])
    params = list(ants.read_transform(reg["fwdtransforms"][0]).parameters)
    shutil.copy(reg["fwdtransforms"][0], work / "transform.mat")
    np.save(work / "aligned.npy", aligned)
    (work / "result.json").write_text(json.dumps({"before": before, "after": after, "rotation_deg": _angle_deg(params[:9]),
                                                  "shift": float(np.linalg.norm(params[9:12])), "ants_version": ants.__version__}))


def warp(work: Path) -> None:
    """Carries a label volume (labels.npy) onto the fixed scan with transform.mat, nearest label only; writes warped.npy."""
    import ants
    import numpy as np
    d1, labels = np.load(work / "fixed.npy"), np.load(work / "labels.npy")
    zooms = tuple(json.loads((work / "zooms.json").read_text()))
    fixed = ants.from_numpy(np.ascontiguousarray(d1), spacing=zooms)
    moving = ants.from_numpy(labels.astype("float32"), spacing=zooms)
    out = ants.apply_transforms(fixed=fixed, moving=moving, transformlist=[str(work / "transform.mat")], interpolator="genericLabel")
    np.save(work / "warped.npy", np.rint(out.numpy()).astype("int8"))


if __name__ == "__main__":
    {"register": register, "warp": warp}[sys.argv[1]](Path(sys.argv[2]))
