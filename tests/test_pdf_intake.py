import hashlib

import pytest
from conftest import sign_in
from pdf_fixtures import make_pdf

from app.ai import gateway
from app.db import SourceFile
from app.pdf_intake import PDFRejected, parse_pdf
from app.pdf_worker import Rejected, parse


def upload(client, data=None, **kw):
    return client.post(
        "/api/patients/patient-demo/documents/pdf",
        data={
            "title": "Fictional PDF",
            "source_date": "2026-11-05",
            "synthetic": "true",
            **kw,
        },
        files={
            "file": (
                "source.pdf",
                data or make_pdf("Appointment date: 2026-11-18."),
                "application/pdf",
            )
        },
    )


def test_pdf_subprocess_and_rejections():
    assert (
        parse_pdf(make_pdf("Fictional appointment source"))["pages"][0]["text"]
        == "Fictional appointment source"
    )
    with pytest.raises(PDFRejected):
        parse_pdf(b"not a pdf")
    for data in [
        make_pdf(pages=11),
        make_pdf("secret", encrypted=True),
        make_pdf("text", javascript=True),
    ]:
        with pytest.raises(Rejected):
            parse(data)


def test_scanned_or_blank_and_limits():
    r = parse(make_pdf())
    assert r["status"] == "ocr_required" and r["text"] == ""
    assert (
        parse(make_pdf(["Some source text", ""], pages=2))["status"] == "ocr_required"
    )
    with pytest.raises(Rejected):
        parse(make_pdf("x" * 12001))


def test_pdf_upload_download_and_scope(client):
    sign_in(client, "family")
    assert upload(client).status_code == 403
    sign_in(client, "clinician")
    data = make_pdf(
        ["Appointment date: 2026-11-18.", "Support requested: transport assistance."],
        pages=2,
    )
    r = upload(client, data)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["payload"]["page_count"] == 2 and doc["payload"]["has_original_file"]
    assert doc["payload"]["file_sha256"] == hashlib.sha256(data).hexdigest()
    url = f"/api/patients/patient-demo/documents/{doc['id']}/file"
    download = client.get(url)
    assert (
        download.content == data
        and "attachment" in download.headers["content-disposition"]
    )
    sign_in(client, "family")
    assert client.get(url).status_code == 403
    sign_in(client, "other")
    assert client.get(url).status_code == 403


def test_pdf_invalid_size_type_encryption(client):
    sign_in(client, "clinician")
    assert upload(client, b"%PDF-" + b"x" * (5 * 1024 * 1024)).status_code == 413
    assert upload(client, b"not-pdf").status_code == 422
    assert upload(client, make_pdf("hidden", encrypted=True)).status_code == 422
    assert upload(client, synthetic="false").status_code == 422
    r = client.post(
        "/api/patients/patient-demo/documents/pdf",
        data={"title": "Fictional", "source_date": "2026-11-05", "synthetic": "true"},
        files={"file": ("bad.pdf", b"%PDF-", "text/plain")},
    )
    assert r.status_code == 415


def test_no_text_does_not_call_model(client, monkeypatch):
    sign_in(client, "clinician")
    doc = upload(client, make_pdf()).json()

    async def forbidden(*a, **kw):
        raise AssertionError("Model must not be called")

    monkeypatch.setattr(gateway, "structured", forbidden)
    r = client.post(
        f"/api/patients/patient-demo/documents/{doc['id']}/extract",
        json={"expected_version": 1},
    )
    assert r.status_code == 409 and doc["status"] == "ocr_required"


def test_pdf_candidate_page_provenance(client, monkeypatch):
    sign_in(client, "clinician")
    doc = upload(
        client,
        make_pdf(
            [
                "Appointment date: 2026-11-18.",
                "Support requested: transport assistance.",
            ],
            pages=2,
        ),
    ).json()

    async def model(*a, **kw):
        return {
            "facts": [
                {
                    "label": "Support",
                    "value": "transport assistance",
                    "unit": "",
                    "quote": "Support requested: transport assistance.",
                }
            ]
        }

    monkeypatch.setattr(gateway, "structured", model)
    r = client.post(
        f"/api/patients/patient-demo/documents/{doc['id']}/extract",
        json={"expected_version": 1},
    )
    assert r.status_code == 200 and r.json()["payload"]["candidates"][0][
        "page_numbers"
    ] == [2]


def test_stored_integrity_failure_blocks_download(client, database):
    sign_in(client, "clinician")
    doc = upload(client).json()
    with database() as db:
        file = db.get(SourceFile, doc["id"])
        file.data = b"tampered"
        db.commit()
    assert (
        client.get(f"/api/patients/patient-demo/documents/{doc['id']}/file").status_code
        == 409
    )
