import io
import math
import struct
import uuid
import wave

import pytest
from conftest import sign_in

from app.db import Audit, CareAudio, CareMessage, Grant, Patient

BASE = "/api/patients/patient-demo/messages"


def wav(seconds=0.5, rate=24000, channels=1, width=2, silent=False):
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(width)
        audio.setframerate(rate)
        frames = int(rate * seconds)
        pcm = (
            b"\0" * frames * channels * width
            if silent or width != 2
            else b"".join(
                struct.pack("<h", int(5000 * math.sin(i * 2 * math.pi * 440 / rate)))
                * channels
                for i in range(frames)
            )
        )
        audio.writeframes(pcm)
    return out.getvalue()


def upload(
    client,
    data=None,
    peer="family",
    key=None,
    caption="Synthetic voice note",
    mime="audio/wav",
):
    return client.post(
        BASE + f"/threads/{peer}/voice",
        data={"command_id": key or str(uuid.uuid4()), "caption": caption},
        files={"audio": ("note.wav", data if data is not None else wav(), mime)},
    )


def test_voice_round_trip_private_playback_and_no_implicit_ack(
    client, database, monkeypatch
):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Voice notes must not call a speech or AI provider")

    monkeypatch.setattr("app.ai.gateway.transcribe", forbidden)
    sign_in(client)
    data = wav()
    response = upload(client, data)
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["message_type"] == "voice"
    assert row["voice"]["duration_ms"] == 500
    assert row["state"] == "saved_in_app" and row["opened_at"] is None
    assert "data" not in row["voice"]
    url = row["voice"]["url"]
    assert client.get(url).content == data
    sign_in(client, "family")
    played = client.get(url)
    assert played.status_code == 200 and played.content == data
    assert played.headers["content-type"] == "audio/wav"
    assert played.headers["cache-control"] == "no-store"
    assert played.headers["x-content-type-options"] == "nosniff"
    thread = client.get(BASE + "/threads/participant").json()["messages"]
    assert thread[0]["message_type"] == "voice" and thread[0]["opened_at"] is None
    assert client.get(BASE + "/inbox").json()["unopened"] == 1
    assert (
        client.post(
            BASE + "/threads/participant/opened", json={"message_ids": [row["id"]]}
        ).status_code
        == 200
    )
    assert client.get(BASE + "/inbox").json()["unopened"] == 0
    sign_in(client, "clinician")
    assert client.get(url).status_code == 404
    assert (
        "Synthetic voice note"
        not in client.get("/api/patients/patient-demo/workspace").text
    )
    assert (
        "Synthetic voice note"
        not in client.get("/api/patients/patient-demo/reports/weekly").text
    )
    with database() as db:
        assert db.query(CareAudio).count() == 1
        assert all("Synthetic voice note" not in str(a.detail) for a in db.query(Audit))


def test_voice_idempotence_and_cross_type_conflicts(client, database):
    sign_in(client)
    key = str(uuid.uuid4())
    first = upload(client, key=key)
    assert first.status_code == 200
    assert upload(client, key=key).json() == first.json()
    assert upload(client, data=wav(seconds=0.6), key=key).status_code == 409
    assert upload(client, key=key, caption="Different caption").status_code == 409
    assert upload(client, key=key, peer="clinician").status_code == 409
    assert (
        client.post(
            BASE + "/threads/family",
            json={"command_id": key, "body": "Synthetic voice note"},
        ).status_code
        == 409
    )
    textkey = str(uuid.uuid4())
    assert (
        client.post(
            BASE + "/threads/family", json={"command_id": textkey, "body": "Text"}
        ).status_code
        == 200
    )
    assert upload(client, key=textkey).status_code == 409
    with database() as db:
        assert db.query(CareAudio).count() == 1
        assert db.query(CareMessage).count() == 2


def test_voice_rechecks_both_grants_for_playback_and_retry(client, database):
    sign_in(client)
    key = str(uuid.uuid4())
    row = upload(client, key=key).json()
    with database() as db:
        db.query(Grant).filter_by(
            user_id="family", patient_id="patient-demo"
        ).one().active = False
        db.commit()
    assert client.get(row["voice"]["url"]).status_code == 403
    assert upload(client, key=key).status_code == 403
    sign_in(client, "family")
    assert client.get(row["voice"]["url"]).status_code == 403
    sign_in(client, "other")
    assert client.get(row["voice"]["url"]).status_code == 403


def test_voice_auth_csrf_scope_and_synthetic_gate(client, database):
    assert upload(client).status_code == 401
    sign_in(client)
    client.headers.pop("X-CSRF-Token")
    assert upload(client).status_code == 403
    sign_in(client)
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = False
        db.commit()
    assert upload(client).status_code == 403
    with database() as db:
        db.get(Patient, "patient-demo").synthetic = True
        db.query(Grant).filter_by(
            user_id="participant", patient_id="patient-demo"
        ).one().scopes = ["summary"]
        db.commit()
    assert upload(client).status_code == 403


@pytest.mark.parametrize(
    "case",
    [
        "bad_header",
        "truncated",
        "stereo",
        "wrong_rate",
        "wrong_width",
        "too_long",
        "empty",
        "silent",
        "mime",
        "bytes",
        "request_limit",
    ],
)
def test_invalid_voice_is_rejected_without_saved_rows(client, database, case):
    sign_in(client)
    cases = {
        "bad_header": b"<svg>not audio</svg>",
        "truncated": wav()[:-25],
        "stereo": wav(channels=2),
        "wrong_rate": wav(rate=44100),
        "wrong_width": wav(width=1),
        "too_long": wav(seconds=30.1),
        "empty": wav(seconds=0),
        "silent": wav(silent=True),
        "mime": wav(),
        "bytes": b"x" * (2 * 1024 * 1024 + 1),
        "request_limit": b"x" * (2 * 1024 * 1024 + 65537),
    }
    response = upload(
        client, data=cases[case], mime="audio/mpeg" if case == "mime" else "audio/wav"
    )
    assert response.status_code in {413, 415, 422}, response.text
    with database() as db:
        assert db.query(CareAudio).count() == 0
        assert db.query(CareMessage).count() == 0


def test_metadata_is_stripped_and_audio_only_routes_cannot_fetch_text(client):
    sign_in(client)
    data = wav()
    row = upload(client, data=data + b"PRIVATE TRAILING METADATA").json()
    assert client.get(row["voice"]["url"]).content == data
    text = client.post(
        BASE + "/threads/family", json={"command_id": str(uuid.uuid4()), "body": "Text"}
    ).json()
    assert client.get(BASE + "/voice/" + text["id"]).status_code == 404
    assert (
        client.get(
            "/api/patients/patient-other/messages/voice/" + row["id"]
        ).status_code
        == 403
    )


def test_voice_caption_and_command_validation(client):
    sign_in(client)
    assert upload(client, caption="x" * 2001).status_code == 422
    assert upload(client, caption="bad\0text").status_code == 422
    assert upload(client, key="short").status_code == 422
    assert upload(client, caption="").json()["body"] == "Voice note"


def test_chunked_voice_request_is_bounded_before_multipart_spooling(client):
    sign_in(client)
    boundary = "neurotwin-voice-boundary"

    def chunks():
        yield f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="note.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
        for _ in range(70):
            yield b"x" * 32768
        yield f"\r\n--{boundary}--\r\n".encode()

    response = client.post(
        BASE + "/threads/family/voice",
        content=chunks(),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413
