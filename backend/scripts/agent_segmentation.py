"""Prepare scans for an external segmentation tool, and import its output.

  prepare  MRI_ID[:SCAN]...                writes <out>/<MRI_ID>.nii.gz (or <MRI_ID>_<SCAN>.nii.gz), a single 3D volume with true voxel size
  import   MRI_ID SEG_FILE TOOL VERSION [SCAN]
                                           copies the segmentation into segmentations/<MRI_ID>/ with tool.json; with SCAN (mpr-2, mpr-3, mpr-4)
                                           it goes to segmentations/<MRI_ID>/repeats/<SCAN>/ and is used only for the same-session repeat spread.
                                           Use the same tool and version as for mpr-1, or the repeat is left out.

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
    for item in ids:
        mri, _, scan = item.partition(":")
        scan = scan or "mpr-1"
        name = f"{mri}.nii.gz" if scan == "mpr-1" else f"{mri}_{scan}.nii.gz"
        data, _, _, zooms = O._load(mri, scan)
        affine = nib.load(str(O._raw_dir(mri) / f"{scan}.nifti.hdr")).affine  # keep the file's own orientation: tools need it
        nib.save(nib.Nifti1Image(np.asarray(data, np.float32), affine), out / name)
        print("wrote", out / name, "shape", data.shape, "voxel", zooms, "axes", "".join(nib.aff2axcodes(affine)))


def import_seg(mri: str, seg: Path, tool: str, version: str, scan: str = "mpr-1") -> None:
    import nibabel as nib
    from app import agent_analysis as A
    data, _, _, _ = O._load(mri, scan)
    img = nib.load(str(seg))
    arr_shape = img.shape[:3]
    class _S:  # shape holder for the coverage check
        shape = arr_shape
    if not A._covers(_S, img.affine, data.shape, A.scan_affine(mri, scan)):
        sys.exit("The segmentation does not cover the scan's field of view. Segment the file written by the prepare step.")
    dest = O.root() / "segmentations" / mri / ("" if scan == "mpr-1" else f"repeats/{scan}")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(seg, dest / ("seg.nii.gz" if str(seg).endswith(".gz") else "seg.nii"))
    (dest / "tool.json").write_text(json.dumps({"tool": tool, "version": version, "source": "run outside NeuroTwin by the project owner"}, indent=1))
    print("imported", mri, "->", dest)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "prepare":
        prepare(sys.argv[2:], O.root() / "segmentation_inputs")
    elif len(sys.argv) in (6, 7) and sys.argv[1] == "import":
        import_seg(sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5], *(sys.argv[6:7]))
    else:
        sys.exit(__doc__)
