"""Prepare ONE OASIS research subject from a local archive. Never extracts arbitrary archive paths.

Run with --archive PATH --subject OAS1_0001_MR1. Native source files and generated
viewer assets stay in ignored local storage, never in the public frontend directory.
This imports existing FreeSurfer results; it does not run reconstruction or forecast.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

import nibabel as nib
import numpy as np
from nibabel.freesurfer import read_annot, read_geometry, read_morph_data

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "imaging_data"


def parse_stats(path: Path, kind: str, hemisphere: str | None = None) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        p = line.split()
        if kind == "aseg" and len(p) >= 5:
            rows.append({"key": f"aseg:{p[1]}", "label_id": int(p[1]), "name": p[4],
                         "volume": float(p[3]), "hemisphere": None, "kind": "subcortical"})
        elif kind == "aparc" and len(p) >= 6:
            rows.append({"key": f"{hemisphere}:{p[0]}", "name": p[0], "hemisphere": hemisphere,
                         "area": float(p[2]), "volume": float(p[3]), "thickness": float(p[4]),
                         "kind": "cortical"})
    return rows


def prepare(archive: Path, subject: str, root: Path = DEFAULT_ROOT) -> Path:
    if not re.fullmatch(r"OAS1_\d{4}_MR\d+", subject):
        raise ValueError("Expected an OASIS-1 subject/visit ID.")
    root.mkdir(parents=True, exist_ok=True)
    target = root / subject
    if target.exists():
        raise ValueError("Prepared subject already exists. Choose a new output root to reprepare.")
    required = {"mri/orig.mgz", "mri/T1.mgz", "mri/aseg.mgz", "stats/aseg.stats"}
    for hemi in ("lh", "rh"):
        required.update({f"surf/{hemi}.{surface}" for surface in ("pial", "white", "inflated", "thickness")})
        required.update({f"label/{hemi}.aparc.annot", f"stats/{hemi}.aparc.stats"})
    optional = {"scripts/build-stamp.txt", "scripts/recon-all.log", "scripts/recon-all.done"}
    checksums = {}
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=root) as tmp:
        work = Path(tmp)
        source, assets = work / "source", work / "assets"
        assets.mkdir()
        prefix = f"disc1/{subject}/"
        with tarfile.open(archive, "r|gz") as tf:
            found = False
            for member in tf:
                if found and member.name.startswith("disc1/OAS1_") and not member.name.startswith(prefix) and member.name != prefix[:-1]:
                    break
                if not member.name.startswith(prefix):
                    continue
                found = True
                rel = member.name[len(prefix):]
                if rel not in required | optional or not member.isfile():
                    continue
                if member.size > 100_000_000:
                    raise ValueError("Unexpected source artifact size.")
                dest = source / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as stream, dest.open("wb") as out:
                    shutil.copyfileobj(stream, out)
                checksums[rel] = hashlib.sha256(dest.read_bytes()).hexdigest()
        missing = required - checksums.keys()
        if missing:
            raise ValueError(f"Missing required artifacts: {sorted(missing)}")
        image, seg = nib.load(source / "mri/T1.mgz"), nib.load(source / "mri/aseg.mgz")
        if image.shape != seg.shape or not np.allclose(image.affine, seg.affine):
            raise ValueError("MRI and segmentation geometry disagree.")
        original = nib.load(source / "mri/orig.mgz")
        if image.shape != original.shape or not np.allclose(image.header.get_vox2ras_tkr(), original.header.get_vox2ras_tkr()):
            raise ValueError("Surface reference and display volume geometry disagree.")
        data = np.asarray(image.dataobj, dtype=np.float32)
        # Working display volume only. Native MRI and its full intensities remain in source/.
        display = np.clip(data, 0, 255).astype("u1")
        labels = np.asarray(seg.dataobj).astype("<u2")
        (assets / "volume.bin").write_bytes(display.tobytes(order="C"))
        (assets / "labels.bin").write_bytes(labels.tobytes(order="C"))
        stats = parse_stats(source / "stats/aseg.stats", "aseg")
        surfaces = []
        for hemi in ("lh", "rh"):
            annotation, colors, names = read_annot(source / f"label/{hemi}.aparc.annot")
            thickness = read_morph_data(source / f"surf/{hemi}.thickness")
            regions = [{"name": n.decode(), "color": c[:3].tolist(), "key": f"{hemi}:{n.decode()}"}
                       for n, c in zip(names, colors)]
            (assets / f"{hemi}.regions.json").write_text(json.dumps(regions))
            (assets / f"{hemi}.annotation.bin").write_bytes(annotation.astype("<i4").tobytes())
            (assets / f"{hemi}.thickness.bin").write_bytes(thickness.astype("<f4").tobytes())
            for surface in ("pial", "white", "inflated"):
                vertices, faces = read_geometry(source / f"surf/{hemi}.{surface}")
                if len(vertices) != len(annotation) or len(vertices) != len(thickness):
                    raise ValueError("Surface annotations do not match vertex count.")
                stem = f"{hemi}.{surface}"
                (assets / f"{stem}.vertices.bin").write_bytes(vertices.astype("<f4").tobytes())
                (assets / f"{stem}.faces.bin").write_bytes(faces.astype("<u4").tobytes())
                surfaces.append({"hemisphere": hemi, "type": surface, "stem": stem,
                                 "vertices": len(vertices), "triangles": len(faces)})
            stats.extend(parse_stats(source / f"stats/{hemi}.aparc.stats", "aparc", hemi))
        version = "Unknown — legacy provided derivatives"
        stamp = source / "scripts/build-stamp.txt"
        log = source / "scripts/recon-all.log"
        if stamp.exists():
            version = stamp.read_text(errors="replace").strip()[:240]
        elif log.exists():
            matches = re.findall(r"(?:freesurfer-[^\r\n]+|build stamp[^\r\n]+)", log.read_text(errors="replace"), re.I)
            if matches:
                version = matches[0][:240]
        manifest = {"schema": 1, "subject": subject, "dataset": "OASIS-1", "visit": subject.split("_")[-1],
                    "status": "Imported derivatives • QC not yet reviewed", "engine_version": version,
                    "shape": [int(v) for v in image.shape], "voxel_to_surface_ras": image.header.get_vox2ras_tkr().tolist(),
                    "voxel_to_scanner_ras": image.affine.tolist(), "volume_dtype": "uint8",
                    "labels_dtype": "uint16-le", "array_order": "C", "surfaces": surfaces,
                    "measurements": stats, "source_checksums": checksums,
                    "source_archive": archive.name,
                    "limitations": ["One structural MRI visit; no longitudinal comparison or forecast.",
                                    "Imported FreeSurfer measurements are not independently quality-reviewed.",
                                    "Inflated surfaces are illustrative geometry and cannot align with MRI slices."]}
        (assets / "manifest.json").write_text(json.dumps(manifest, indent=2))
        work.rename(target)
        # TemporaryDirectory tolerates the moved working directory.
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--subject", default="OAS1_0001_MR1")
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(prepare(args.archive, args.subject, args.output))
