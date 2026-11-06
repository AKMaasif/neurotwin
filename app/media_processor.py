"""Bounded subprocess media validation/reconstruction; never serves source objects."""

import csv
import hashlib
import io
import json
import math
import sys
import warnings
import wave
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 16000000


def waveform(pcm):
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    return [
        round(float(np.sqrt(np.mean(a * a))) / 32768, 4) if len(a) else 0
        for a in np.array_split(samples, 64)
    ]


def image(source, out, ext):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source) as im:
            expected = {
                ".jpg": "JPEG",
                ".jpeg": "JPEG",
                ".png": "PNG",
                ".webp": "WEBP",
            }[ext]
            if im.format != expected or im.width * im.height > 16000000:
                raise ValueError("image_signature_or_dimensions")
            im.load()
            im = ImageOps.exif_transpose(im).convert("RGB")
            width, height = im.size
            im.save(out, format="JPEG", quality=90)
            im.thumbnail((640, 640))
            im.save(str(out) + ".thumb", format="JPEG", quality=80)
    return {
        "content_type": "image/jpeg",
        "extension": ".jpg",
        "width": width,
        "height": height,
        "thumbnail": True,
    }


def audio_video(source, out, ext, kind):
    import av

    start = source.read_bytes()[:16]
    if ext in {".wav"} and (start[:4] != b"RIFF" or start[8:12] != b"WAVE"):
        raise ValueError("audio_signature")
    if ext in {".mp4", ".m4a"} and start[4:8] != b"ftyp":
        raise ValueError("mp4_signature")
    if ext == ".webm" and not start.startswith(b"\x1aE\xdf\xa3"):
        raise ValueError("webm_signature")
    if ext == ".ogg" and not start.startswith(b"OggS"):
        raise ValueError("ogg_signature")
    with av.open(str(source)) as inp:
        if len(inp.streams) > 3 or any(
            s.type not in {"audio", "video"} for s in inp.streams
        ):
            raise ValueError("unsupported_media_stream")
        if inp.duration and inp.duration / av.time_base > 120.5:
            raise ValueError("media_duration")
        if kind in {"audio", "voice"}:
            if inp.streams.video or len(inp.streams.audio) != 1:
                raise ValueError("audio_streams")
            valid = {
                ".wav": {"wav"},
                ".mp3": {"mp3"},
                ".m4a": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
                ".ogg": {"ogg"},
                ".webm": {"matroska", "webm"},
            }
            if not set(inp.format.name.split(",")) & valid[ext]:
                raise ValueError("audio_container")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=24000)
            pcm = bytearray()
            for frame in inp.decode(audio=0):
                for rendered in resampler.resample(frame):
                    pcm.extend(rendered.to_ndarray().astype("<i2").tobytes())
                    if len(pcm) > 24000 * 2 * (30 if kind == "voice" else 120):
                        raise ValueError("media_duration")
            for rendered in resampler.resample(None):
                pcm.extend(rendered.to_ndarray().astype("<i2").tobytes())
            if (
                not pcm
                or not any(pcm)
                or len(pcm) > 24000 * 2 * (30 if kind == "voice" else 120)
            ):
                raise ValueError("empty_or_long_audio")
            with wave.open(str(out), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(24000)
                target.writeframes(pcm)
            return {
                "content_type": "audio/wav",
                "extension": ".wav",
                "duration_ms": round(len(pcm) / 48),
                "waveform": waveform(pcm),
            }
        if ext not in {".mp4", ".webm"} or len(inp.streams.video) != 1:
            raise ValueError("video_container")
        allowed = {"h264", "vp8", "vp9", "aac", "opus", "vorbis"}
        if any(s.codec_context.name not in allowed for s in inp.streams):
            raise ValueError("video_codec")
        stream = inp.streams.video[0]
        if not 0 < stream.width <= 1920 or not 0 < stream.height <= 1920:
            raise ValueError("video_dimensions")
        duration = 0
        count = 0
        thumb = False
        with av.open(
            str(out), "w", format="mp4" if ext == ".mp4" else "webm"
        ) as output:
            mapping = {s.index: output.add_stream_from_template(s) for s in inp.streams}
            for s in mapping.values():
                s.metadata.clear()
            for packet in inp.demux():
                index = packet.stream.index
                for frame in packet.decode():
                    duration = max(duration, float(frame.time or 0))
                    if isinstance(frame, av.VideoFrame):
                        if frame.width > 1920 or frame.height > 1920:
                            raise ValueError("video_dimensions")
                        count += 1
                        if not thumb:
                            im = frame.to_image()
                            im.thumbnail((640, 640))
                            im.save(str(out) + ".thumb", format="JPEG", quality=80)
                            thumb = True
                    if count > 7200 or duration > 120.5:
                        raise ValueError("video_duration")
                if packet.dts is not None:
                    packet.stream = mapping[index]
                    output.mux(packet)
        if not count:
            raise ValueError("empty_video")
        duration = max(duration, float(inp.duration or 0) / av.time_base)
        return {
            "content_type": "video/mp4" if ext == ".mp4" else "video/webm",
            "extension": ext,
            "width": stream.width,
            "height": stream.height,
            "duration_ms": round(duration * 1000),
            "thumbnail": thumb,
        }


def document(source, out, ext):
    data = source.read_bytes()
    if ext == ".pdf":
        import pypdfium2 as pdfium
        from pypdf import PdfReader

        if not data.startswith(b"%PDF-"):
            raise ValueError("pdf_signature")
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("encrypted_document")
        root = reader.trailer["/Root"]
        if any(k in root for k in ["/OpenAction", "/AA"]) or any(
            k in root.get("/Names", {}) for k in ["/JavaScript", "/EmbeddedFiles"]
        ):
            raise ValueError("active_document")
        pdf = pdfium.PdfDocument(data)
        pages = []
        total = 0
        try:
            if not 0 < len(pdf) <= 20:
                raise ValueError("document_pages")
            for page in pdf:
                width, height = page.get_size()
                pixels = math.ceil(width * 4 / 3) * math.ceil(height * 4 / 3)
                total += pixels
                if pixels > 4000000 or total > 40000000:
                    raise ValueError("document_dimensions")
                bitmap = page.render(scale=4 / 3, draw_annots=False)
                pages.append(bitmap.to_pil().convert("RGB"))
                bitmap.close()
                page.close()
            pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:])
            im = pages[0].copy()
            im.thumbnail((480, 640))
            im.save(str(out) + ".thumb", format="JPEG")
            return {
                "content_type": "application/pdf",
                "extension": ".pdf",
                "pages": len(pages),
                "thumbnail": True,
                "reconstruction": "raster_pdf",
            }
        finally:
            for page in pages:
                page.close()
            pdf.close()
    if ext in {".docx", ".xlsx"}:
        from defusedxml import ElementTree

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > 1500
                or sum(i.file_size for i in entries) > 40 * 1024 * 1024
                or any(
                    i.file_size > 10 * 1024 * 1024
                    or i.file_size / max(1, i.compress_size) > 150
                    for i in entries
                )
            ):
                raise ValueError("expanded_document_limit")
            required = "word/document.xml" if ext == ".docx" else "xl/workbook.xml"
            if required not in archive.namelist():
                raise ValueError("office_signature")
            for entry in entries:
                lower = entry.filename.lower()
                if any(
                    x in lower for x in ["vbaproject", "embeddings/", "externallinks/"]
                ):
                    raise ValueError("active_document")
                if lower.endswith((".xml", ".rels")):
                    tree = ElementTree.fromstring(archive.read(entry))
                    if any(
                        e.attrib.get("TargetMode") == "External" for e in tree.iter()
                    ):
                        raise ValueError("external_document_relationship")
        if ext == ".docx":
            from docx import Document

            original = Document(io.BytesIO(data))
            clean = Document()
            if len(original.paragraphs) > 10000 or len(original.tables) > 100:
                raise ValueError("document_limit")
            for p in original.paragraphs:
                clean.add_paragraph(p.text)
            for table in original.tables:
                if len(table.rows) * len(table.columns) > 10000:
                    raise ValueError("document_limit")
                result = clean.add_table(rows=0, cols=len(table.columns))
                for row in table.rows:
                    cells = result.add_row().cells
                    for index, cell in enumerate(row.cells):
                        cells[index].text = cell.text
            clean.save(out)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            from openpyxl import Workbook, load_workbook

            original = load_workbook(
                io.BytesIO(data), read_only=True, data_only=False, keep_links=False
            )
            clean = Workbook()
            clean.remove(clean.active)
            count = 0
            if len(original.worksheets) > 8:
                raise ValueError("document_limit")
            for sheet in original:
                if sheet.max_row > 5000 or sheet.max_column > 64:
                    raise ValueError("document_limit")
                target = clean.create_sheet(sheet.title)
                for row in sheet.iter_rows():
                    values = []
                    for cell in row:
                        count += 1
                        if count > 50000 or cell.data_type == "f":
                            raise ValueError("formula_or_document_limit")
                        values.append(cell.value)
                    target.append(values)
            clean.save(out)
            original.close()
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return {
            "content_type": mime,
            "extension": ext,
            "reconstruction": "text_values_only",
        }
    text = data.decode("utf-8-sig")
    if any(ord(c) < 32 and c not in "\t\r\n" for c in text):
        raise ValueError("invalid_text")
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(text)))
        if len(rows) > 10000 or sum(len(r) for r in rows) > 50000:
            raise ValueError("document_limit")
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in rows:
            writer.writerow(
                [
                    "'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v
                    for v in row
                ]
            )
        text = buf.getvalue()
    out.write_text(text, encoding="utf-8")
    return {
        "content_type": "text/csv" if ext == ".csv" else "text/plain",
        "extension": ext,
        "reconstruction": "utf8_text",
    }


def run(source, out, kind, extension):
    if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in source.read_bytes():
        raise ValueError("known_malware_signature")
    if kind == "image":
        result = image(source, out, extension)
    elif kind in {"voice", "audio", "video"}:
        result = audio_video(source, out, extension, kind)
    else:
        result = document(source, out, extension)
    result.update(
        bytes=out.stat().st_size, sha256=hashlib.sha256(out.read_bytes()).hexdigest()
    )
    return result


if __name__ == "__main__":
    try:
        result = run(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4])
        print(json.dumps({"ok": True, "detail": result}))
    except Exception:
        # Raw parser errors/filenames/content never escape into application logs.
        print(json.dumps({"ok": False, "error": "unsafe_or_unsupported_media"}))
        raise SystemExit(1)
