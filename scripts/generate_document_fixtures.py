"""Generate fictional local browser fixtures; never reads real patient documents."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from document_fixtures import (
    docx_bytes,
    image_bytes,
    scanned_pdf,
    xls_bytes,
    xlsx_bytes,
)
from pdf_fixtures import make_pdf


def main():
    out = Path(__file__).resolve().parents[1] / "test-results" / "document-fixtures"
    out.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "appointment.docx": docx_bytes(True),
        "activities.xlsx": xlsx_bytes(),
        "legacy.xls": xls_bytes(),
        "schedule.csv": b"Activity,Date\nTransport assistance,2026-11-18\nFamily call,2026-11-19",
        "note.txt": b"Fictional support note. Transport assistance requested.",
        "scan.pdf": scanned_pdf(),
        "mixed.pdf": scanned_pdf(True),
        "appointment.png": image_bytes(),
        "text.pdf": make_pdf("Appointment date: 2026-11-18."),
    }
    for name, data in fixtures.items():
        (out / name).write_bytes(data)
    print("Fictional browser fixtures prepared:", len(fixtures))


if __name__ == "__main__":
    main()
