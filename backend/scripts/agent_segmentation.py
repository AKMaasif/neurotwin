"""Prepare scans for an external segmentation tool, and import its output.

  prepare  MRI_ID...                       writes <out>/<MRI_ID>.nii.gz (single 3D volume, true voxel size)
  import   MRI_ID SEG_FILE TOOL VERSION    copies the segmentation into segmentations/<MRI_ID>/ with tool.json

The tool itself (SynthSeg) is run by you, outside NeuroTwin. See docs/AGENT_ANALYSIS_SEGMENTATION.md.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import oasis2_api as O  # noqa: E402


def prepare(ids: list[str], out: Path) -> None:
    import nibabel as nib
    import numpy as np
    out.mkdir(parents=True, exist_ok=True)
    for mri in ids:
        data, _, _, zooms = O._load(mri, "mpr-1")
        nib.save(nib.Nifti1Image(np.asarray(data, np.float32), np.diag([*zooms, 1.0])), out / f"{mri}.nii.gz")
        print("wrote", out / f"{mri}.nii.gz", "shape", data.shape, "voxel", zooms)


def import_seg(mri: str, seg: Path, tool: str, version: str) -> None:
    import nibabel as nib
    data, _, _, _ = O._load(mri, "mpr-1")
    got = nib.load(str(seg)).shape
    got = got[:3] if len(got) > 3 and got[3] == 1 else got
    if tuple(got) != tuple(data.shape):
        sys.exit(f"Segmentation shape {got} does not match the scan {data.shape}. Use the output in the input's own space.")
    dest = O.root() / "segmentations" / mri
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(seg, dest / ("seg.nii.gz" if str(seg).endswith(".gz") else "seg.nii"))
    (dest / "tool.json").write_text(json.dumps({"tool": tool, "version": version, "source": "run outside NeuroTwin by the project owner"}, indent=1))
    print("imported", mri, "->", dest)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "prepare":
        prepare(sys.argv[2:], O.root() / "segmentation_inputs")
    elif len(sys.argv) == 6 and sys.argv[1] == "import":
        import_seg(sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5])
    else:
        sys.exit(__doc__)
