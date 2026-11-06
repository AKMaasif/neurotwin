"""Small synthetic files for actual media/database/browser integration checks."""

import io
import math
import struct
import wave
from pathlib import Path


def fixture(extension):
    out = io.BytesIO()
    if extension in {"jpg", "png", "webp"}:
        from PIL import Image

        Image.new("RGB", (80, 60), (75, 112, 155)).save(
            out, format={"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[extension]
        )
    elif extension == "pdf":
        from pypdf import PdfWriter

        pdf = PdfWriter()
        pdf.add_blank_page(width=300, height=250)
        pdf.write(out)
    elif extension == "docx":
        from docx import Document

        doc = Document()
        doc.add_paragraph(
            "Synthetic appointment preparation. No clinical instructions."
        )
        doc.save(out)
    elif extension == "xlsx":
        from openpyxl import Workbook

        book = Workbook()
        book.active.append(["Synthetic activity", "Recorded"])
        book.active.append(["Call family", "Yes"])
        book.save(out)
    elif extension == "txt":
        out.write(b"Synthetic appointment information. No real patient data.")
    elif extension == "csv":
        out.write(b"activity,confirmation\ncall family,reported\n")
    elif extension == "wav":
        rate = 24000
        pcm = b"".join(
            struct.pack("<h", round(4000 * math.sin(2 * math.pi * 440 * i / rate)))
            for i in range(rate)
        )
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(pcm)
    elif extension in {"mp4", "webm"}:
        import av
        import numpy as np

        with av.open(out, "w", format=extension) as movie:
            stream = movie.add_stream(
                "libx264" if extension == "mp4" else "libvpx-vp9", rate=10
            )
            stream.width = 160
            stream.height = 120
            stream.pix_fmt = "yuv420p"
            for index in range(10):
                frame = av.VideoFrame.from_ndarray(
                    np.full((120, 160, 3), index * 20, dtype=np.uint8), format="rgb24"
                )
                for packet in stream.encode(frame):
                    movie.mux(packet)
            for packet in stream.encode():
                movie.mux(packet)
    elif extension in {"mp3", "m4a", "ogg"}:
        import av
        import numpy as np

        rate = 48000
        codec = {"mp3": "libmp3lame", "m4a": "aac", "ogg": "libopus"}[extension]
        with av.open(
            out, "w", format="mp4" if extension == "m4a" else extension
        ) as audio:
            stream = audio.add_stream(codec, rate=rate)
            stream.layout = "mono"
            samples = (
                (4000 * np.sin(2 * np.pi * 440 * np.arange(rate) / rate))
                .astype(np.int16)
                .reshape(1, -1)
            )
            frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
            frame.sample_rate = rate
            for packet in stream.encode(frame):
                audio.mux(packet)
            for packet in stream.encode():
                audio.mux(packet)
    else:
        raise ValueError("Unsupported fixture")
    return out.getvalue()


if __name__ == "__main__":
    target = Path("test-results/chat-fixtures")
    target.mkdir(parents=True, exist_ok=True)
    for ext in [
        "jpg",
        "png",
        "webp",
        "pdf",
        "docx",
        "xlsx",
        "txt",
        "csv",
        "wav",
        "mp3",
        "m4a",
        "ogg",
        "mp4",
        "webm",
    ]:
        (target / ("synthetic." + ext)).write_bytes(fixture(ext))
    print("Generated synthetic chat fixtures under ignored test-results.")
