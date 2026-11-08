"""Fetch only the CC0 author-deposited SATURN data/dictionary to ignored storage."""

import hashlib
import json
from pathlib import Path

import httpx

FILES = {
    "SATURN_DATA_2020_06JUN_24_DATA_worksheet.csv": "ea4fcc55d829a47ea7ca04fb17c031ab",
    "SATURN_DATA_2020_06JUN_24_INFO_worksheet.csv": "b0fa655a0a4267241b6704ca82012b2e",
}


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "data" / "ml-source"
    output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=45) as client:
        response = client.get("https://zenodo.org/api/records/3962060")
        response.raise_for_status()
        metadata = response.json()
        if metadata["metadata"]["license"]["id"] != "cc-zero":
            raise ValueError("Source permission changed; review before downloading")
        for name, expected in FILES.items():
            item = next(f for f in metadata["files"] if f["key"] == name)
            if item["checksum"] != "md5:" + expected:
                raise ValueError("Published source file changed")
            response = client.get(item["links"]["self"])
            response.raise_for_status()
            content = response.content
            if len(content) > 2_000_000 or hashlib.md5(content).hexdigest() != expected:
                raise ValueError("Source checksum mismatch")
            target = output / (
                "saturn-original.csv" if "DATA_worksheet" in name else "saturn-info.csv"
            )
            if target.exists() and target.read_bytes() != content:
                raise ValueError("Existing private source differs; refusing overwrite")
            target.write_bytes(content)
    (output / "source-metadata.json").write_text(
        json.dumps(
            dict(
                source="https://zenodo.org/records/3962060",
                doi="10.5061/dryad.02v6wwpzr",
                license="CC0-1.0",
                files=FILES,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Verified two author-deposited CC0 source files in ignored local storage.")


if __name__ == "__main__":
    main()
