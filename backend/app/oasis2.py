"""OASIS-2 session table and archive manifest.

Reads the dataset's own demographic table and the file listing of the raw archives and states, per subject and visit,
what is actually there. Nothing is guessed: visit order and elapsed time come from the table's `MR Delay` column (days),
missing values stay missing, and a visit without a usable scan is reported as such. The Group column is dataset
metadata that was assigned using later information, so it is kept for description only.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

IMPORTED_FIELDS = ("eTIV", "nWBV", "ASF")  # supplied by OASIS, not measured by NeuroTwin
SCAN = re.compile(r"(?:^|/)(OAS2_\d{4})_MR(\d+)/RAW/(mpr-\d+)\.nifti\.(hdr|img)$")
HEADER_BYTES = 348
DAYS_PER_YEAR = 365.25


def load_table(path: str | Path) -> list[dict]:
    """Sessions from `Demographic Data.xlsx`, ordered by subject then elapsed days. Blank cells become None."""
    import openpyxl
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = list(sheet.iter_rows(values_only=True))
    head = [str(h).strip() for h in rows[0]]
    out = []
    for raw in rows[1:]:
        if not raw or raw[0] is None:
            continue
        rec = {h: (None if v == "" else v) for h, v in zip(head, raw)}
        rec.pop("Visit", None)  # a formula over the ID; order is taken from MR Delay
        out.append(rec)
    out.sort(key=lambda r: (r["Subject ID"], r["MR Delay"]))
    return out


def parse_listing(lines: list[str]) -> list[tuple[str, int]]:
    """(path, size) pairs from `tar -tv` lines: perms owner size date time path."""
    files = []
    for line in lines:
        parts = line.split(None, 5)
        if len(parts) == 6 and parts[0].startswith("-"):
            try:
                files.append((parts[5].rstrip("\n"), int(parts[2])))
            except ValueError:
                continue
    return files


def index_scans(files: list[tuple[str, int]]) -> dict[str, dict[str, dict]]:
    """mri_id -> scan name -> {hdr: size, img: size, path_hdr, path_img} for the raw acquisitions."""
    found: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    for path, size in files:
        m = SCAN.search(path)
        if not m:
            continue
        subject, visit, scan, kind = m.groups()
        found[f"{subject}_MR{visit}"][scan][kind] = size
        found[f"{subject}_MR{visit}"][scan][f"path_{kind}"] = path
    return {k: dict(v) for k, v in found.items()}


def _scan_usable(entry: dict) -> tuple[bool, str | None]:
    if "hdr" not in entry or "img" not in entry:
        return False, "header or image file missing"
    if entry["hdr"] != HEADER_BYTES:
        return False, f"header is {entry['hdr']} bytes, expected {HEADER_BYTES}"
    if entry["img"] <= 0:
        return False, "image file is empty"
    return True, None


def build_manifest(table: list[dict], scans: dict[str, dict[str, dict]]) -> dict:
    """Join the table to the archive listing. Each visit gets a status and the reasons for it."""
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for r in table:
        by_subject[r["Subject ID"]].append(r)
    table_ids = {r["MRI ID"] for r in table}

    subjects = []
    for sid, sessions in sorted(by_subject.items()):
        sessions.sort(key=lambda r: r["MR Delay"])
        visits, previous = [], None
        for r in sessions:
            entries = scans.get(r["MRI ID"], {})
            checked = {name: _scan_usable(e) for name, e in sorted(entries.items())}
            usable = [n for n, (ok, _) in checked.items() if ok]
            problems = [f"{n}: {why}" for n, (ok, why) in checked.items() if not ok]
            if not entries:
                status, problems = "no_scan_in_archives", problems + ["no raw acquisition found in the supplied archives"]
            elif not usable:
                status = "unusable"
            else:
                status = "usable"
            gap = None if previous is None else round((r["MR Delay"] - previous) / DAYS_PER_YEAR, 3)
            visits.append({
                "mri_id": r["MRI ID"], "delay_days": r["MR Delay"], "years_since_previous": gap, "status": status,
                "usable_scans": usable, "problems": problems,
                "clinical": {k: r.get(k) for k in ("Age", "M/F", "EDUC", "SES", "MMSE", "CDR")},
                "imported_measures": {k: r.get(k) for k in IMPORTED_FIELDS},
            })
            previous = r["MR Delay"]
        ok_visits = [v for v in visits if v["status"] == "usable"]
        subjects.append({
            "subject_id": sid, "group_label_from_dataset": sessions[0].get("Group"), "visits": visits,
            "level1_compare": len(ok_visits) >= 2,
            "level2_trend": len(ok_visits) >= 3,
        })
    archive_only = sorted(set(scans) - table_ids)
    return {
        "subjects": subjects,
        "archive_visits_not_in_table": archive_only,
        "summary": {
            "subjects": len(subjects), "sessions_in_table": len(table),
            "visits_usable": sum(v["status"] == "usable" for s in subjects for v in s["visits"]),
            "visits_without_scan": sum(v["status"] == "no_scan_in_archives" for s in subjects for v in s["visits"]),
            "visits_unusable": sum(v["status"] == "unusable" for s in subjects for v in s["visits"]),
            "level1_subjects": sum(s["level1_compare"] for s in subjects),
            "level2_subjects": sum(s["level2_trend"] for s in subjects),
            "archive_visits_not_in_table": len(archive_only),
        },
    }
