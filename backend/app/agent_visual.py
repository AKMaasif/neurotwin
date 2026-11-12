"""Slices for the visual comparison agent: the same picture the viewer shows, chosen by rules, plus a tissue check. No model."""
from __future__ import annotations

import io

from . import agent_analysis as A

AXIS_NAME = {0: "voxel-axis-1", 1: "voxel-axis-2", 2: "voxel-axis-3"}  # the viewer says "voxel axis" too: the file orientation is not assumed
VIEWS = (2, 1)  # axial and coronal


def render_slice(run: dict, layer: str, axis: int, index: int):
    """The grey slice the viewer and the agents see (one display range from the earlier scan, true proportions). None when the layer is missing."""
    import numpy as np
    from PIL import Image
    data = A.layer_volume(run, layer)
    if data is None or not 0 <= index < data.shape[axis]:
        return None
    ref = A.layer_volume(run, "earlier")
    lo, hi = (float(v) for v in np.percentile(ref[ref > 0], [1, 99]))
    gray = np.clip((np.take(data, index, axis=axis) - lo) / max(hi - lo, 1e-6), 0, 1) * 255
    image = Image.fromarray(np.rot90(gray).astype(np.uint8), mode="L")
    zooms = run["validation"]["checks"]["earlier"]["voxel_mm"]
    i, j = [k for k in range(3) if k != axis]
    zi, zj = zooms[i] or 1.0, zooms[j] or 1.0
    if abs(zi - zj) > 1e-3:
        m = min(zi, zj)
        image = image.resize((max(1, round(image.width * zi / m)), max(1, round(image.height * zj / m))), Image.BILINEAR)
    return image


def png(image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def key_slices(run: dict) -> list[dict]:
    """Two positions in each of two viewing directions: where the labelled boundaries differ most after alignment, and the middle of the head."""
    import numpy as np
    e, l = A.layer_labels(run, "earlier_seg"), A.layer_labels(run, "later_seg_aligned")
    vol = A.layer_volume(run, "earlier")
    out = []
    for axis in VIEWS:
        n = vol.shape[axis]
        other = tuple(k for k in range(3) if k != axis)
        mid = n // 2
        picks = []
        if e is not None and l is not None:
            diff = ((e > 0) != (l > 0)).sum(axis=other) + (e != l).sum(axis=other)
            top = int(np.argmax(diff))
            if diff[top] > 0:
                picks.append((top, "largest labelled-boundary difference in this direction"))
        if not picks or abs(picks[0][0] - mid) > 8:
            picks.append((mid, "middle of the head in this direction"))
        for idx, why in picks[:2]:
            out.append({"id": f"S{len(out) + 1}", "axis": axis, "view": AXIS_NAME[axis], "index": int(idx), "reason": why})
    return out


def export(run: dict, slices: list[dict]) -> tuple[list[tuple[str, bytes]], dict]:
    """Earlier and aligned-later PNGs of each slice, in a fixed order, and a tissue mask per slice for checking locations."""
    import numpy as np
    images, masks = [], {}
    for s in slices:
        a, b = render_slice(run, "earlier", s["axis"], s["index"]), render_slice(run, "later_aligned", s["axis"], s["index"])
        if a is None or b is None:
            continue
        images += [(f"{s['id']}_earlier.png", png(a)), (f"{s['id']}_later_aligned.png", png(b))]
        masks[s["id"]] = (np.asarray(a) > 12) | (np.asarray(b) > 12)
        s["size"] = list(a.size)
    return images, masks


def has_tissue(mask, x: float, y: float) -> bool:
    """x and y are fractions of the picture's width and height from the top left. True when the spot, or its close surroundings, shows tissue."""
    h, w = mask.shape
    cx, cy = int(min(max(x, 0), 1) * (w - 1)), int(min(max(y, 0), 1) * (h - 1))
    r = max(2, round(0.01 * max(h, w)))
    return bool(mask[max(cy - r, 0):cy + r + 1, max(cx - r, 0):cx + r + 1].any())
