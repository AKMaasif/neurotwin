import io

import pytest
from PIL import Image, ImageDraw

from app.ai import ProviderUnavailable, gateway
from app.db import Audit, Grant, Patient, Record
from tests.conftest import sign_in

PATH = "/api/patients/patient-demo/camera/check"
HEADERS = {"Content-Type": "image/png", "X-Camera-Consent": "synthetic-camera-1"}


def sample(size=(320, 240)):
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).rectangle((30, 30, 150, 180), fill="blue")
    out = io.BytesIO()
    metadata = Image.Exif()
    metadata[270] = "Synthetic private metadata"
    image.save(out, "PNG", exif=metadata)
    return out.getvalue()


def test_explicit_consent_and_role_boundary(client, monkeypatch):
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Unauthorized provider call")

    monkeypatch.setattr(gateway, "structured", forbidden)
    sign_in(client)
    assert (
        client.post(
            PATH, content=sample(), headers={"Content-Type": "image/png"}
        ).status_code
        == 403
    )
    sign_in(client, "family")
    assert client.post(PATH, content=sample(), headers=HEADERS).status_code == 403
    sign_in(client, "clinician")
    assert client.post(PATH, content=sample(), headers=HEADERS).status_code == 403
    assert calls == []


def test_allowlisted_output_and_no_image_or_scene_retention(
    client, database, monkeypatch
):
    sign_in(client)
    with database() as db:
        before = db.query(Record).count()

    async def model(provider, model, prompt, schema, images):
        assert provider == "gemini"
        assert images[0][0] == "image/jpeg"
        with Image.open(io.BytesIO(images[0][1])) as image:
            assert image.size == (320, 240)
            assert not image.getexif()
        return {"quality": "usable", "objects": [{"object": "cup", "position": "left"}]}

    monkeypatch.setattr(gateway, "structured", model)
    result = client.post(PATH, content=sample(), headers=HEADERS)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "tentative"
    assert "may be a cup" in result.json()["text"]
    assert result.json()["clinical_use"] is False
    with database() as db:
        assert db.query(Record).count() == before
        audit = db.query(Audit).filter_by(action="camera.checked").one()
        assert "cup" not in str(audit.detail)


@pytest.mark.parametrize(
    "body,mime",
    [
        (b"not an image", "image/png"),
        (sample(), "text/html"),
        (sample(), "image/jpeg"),
        (sample((100, 100)), "image/png"),
        (sample((2500, 2000)), "image/png"),
        (b"x" * (1024 * 1024 + 1), "image/png"),
    ],
)
def test_invalid_inputs_never_reach_provider(client, monkeypatch, body, mime):
    sign_in(client)

    async def forbidden(*args, **kwargs):
        raise AssertionError("Invalid image reached provider")

    monkeypatch.setattr(gateway, "structured", forbidden)
    result = client.post(PATH, content=body, headers=HEADERS | {"Content-Type": mime})
    assert result.status_code in {413, 415, 422}


@pytest.mark.parametrize(
    "output",
    [
        {
            "quality": "usable",
            "objects": [{"object": "medication", "position": "left"}],
        },
        {"quality": "usable", "objects": [], "instruction": "walk forward"},
        {"quality": "unclear", "objects": [{"object": "cup", "position": "left"}]},
    ],
)
def test_unsafe_or_inconsistent_output_is_rejected(client, monkeypatch, output):
    sign_in(client)

    async def model(*args, **kwargs):
        return output

    monkeypatch.setattr(gateway, "structured", model)
    result = client.post(PATH, content=sample(), headers=HEADERS)
    assert result.status_code == 503
    assert "medication" not in result.text
    assert "walk forward" not in result.text


def test_uncertainty_and_provider_failure(client, monkeypatch):
    sign_in(client)

    async def unclear(*args, **kwargs):
        return {"quality": "unclear", "objects": []}

    monkeypatch.setattr(gateway, "structured", unclear)
    assert (
        client.post(PATH, content=sample(), headers=HEADERS).json()["status"]
        == "unclear"
    )

    async def failed(*args, **kwargs):
        raise ProviderUnavailable("Private provider response")

    monkeypatch.setattr(gateway, "structured", failed)
    response = client.post(PATH, content=sample(), headers=HEADERS)
    assert response.status_code == 503
    assert "Private provider response" not in response.text


def test_real_patient_cross_patient_and_inflight_revocation(
    client, database, monkeypatch
):
    sign_in(client)
    assert (
        client.post(
            PATH.replace("patient-demo", "patient-other"),
            content=sample(),
            headers=HEADERS,
        ).status_code
        == 403
    )
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = False
        db.commit()
    assert client.post(PATH, content=sample(), headers=HEADERS).status_code == 403

    with database() as db:
        db.get(Patient, "patient-demo").synthetic = True
        db.commit()

    async def revoked(*args, **kwargs):
        with database() as db:
            db.query(Grant).filter_by(
                user_id="participant", patient_id="patient-demo"
            ).one().active = False
            db.commit()
        return {
            "quality": "usable",
            "objects": [{"object": "chair", "position": "center"}],
        }

    monkeypatch.setattr(gateway, "structured", revoked)
    assert client.post(PATH, content=sample(), headers=HEADERS).status_code == 403


def test_streamed_oversize_is_rejected_before_provider(client, monkeypatch):
    sign_in(client)

    async def forbidden(*args, **kwargs):
        raise AssertionError("Oversized stream reached provider")

    monkeypatch.setattr(gateway, "structured", forbidden)
    response = client.post(
        PATH, content=iter([b"x" * 600000, b"x" * 600000]), headers=HEADERS
    )
    assert response.status_code == 413
