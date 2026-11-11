"""Extract chosen subjects' raw scans from an OASIS-2 archive into the local, git-ignored folder.

    python scripts/oasis2_extract.py <archive.tar.gz> OAS2_0001 OAS2_0002 ... [--out imaging_data/oasis2/extracted] [--scans mpr-1]

Reads the archive once and stops as soon as it has passed the last requested subject (archives are ordered by subject),
so early subjects are quick. Only files under <subject>_MR<n>/RAW/ with the chosen scan names are written; member names
are checked so nothing can land outside the output folder.
"""
import argparse
import re
import sys
import tarfile
from pathlib import Path

MEMBER = re.compile(r"^(OAS2_RAW_PART\d)/(OAS2_\d{4})_MR\d{1,2}/RAW/(mpr-\d{1,2})\.nifti\.(hdr|img)$")


def extract(archive: Path, subjects: set[str], out: Path, scans: set[str]) -> int:
    out.mkdir(parents=True, exist_ok=True); written = 0; last = max(subjects)
    with tarfile.open(archive, "r|gz") as tar:
        for member in tar:
            m = MEMBER.match(member.name) if member.isfile() else None
            if m is None:
                sid = re.search(r"(OAS2_\d{4})_MR", member.name)
                if sid and sid.group(1) > last:
                    break  # ordered by subject: nothing wanted remains
                continue
            part, sid, scan, _ = m.groups()
            if sid not in subjects or scan not in scans:
                if sid > last:
                    break
                continue
            target = (out / member.name).resolve()
            if out.resolve() not in target.parents:
                raise ValueError(f"refusing {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, open(target, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("archive"); ap.add_argument("subjects", nargs="+")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "imaging_data" / "oasis2" / "extracted"))
    ap.add_argument("--scans", nargs="+", default=["mpr-1"])
    a = ap.parse_args()
    for s in a.subjects:
        if not re.fullmatch(r"OAS2_\d{4}", s):
            sys.exit(f"not a subject id: {s}")
    n = extract(Path(a.archive), set(a.subjects), Path(a.out), set(a.scans))
    print(f"wrote {n} files to {a.out}")


if __name__ == "__main__":
    main()
