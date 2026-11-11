"""Build the OASIS-2 manifest from the demographic table and `tar -tv` listings of the raw archives.

    python scripts/oasis2_manifest.py "Demographic Data.xlsx" list_part1.txt list_part2.txt -o manifest.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import oasis2  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("table"); ap.add_argument("listings", nargs="+"); ap.add_argument("-o", "--out", default="manifest.json")
    a = ap.parse_args()
    files = []
    for path in a.listings:
        files += oasis2.parse_listing(Path(path).read_text(errors="replace").splitlines())
    manifest = oasis2.build_manifest(oasis2.load_table(a.table), oasis2.index_scans(files))
    Path(a.out).write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest["summary"], indent=1))


if __name__ == "__main__":
    main()
