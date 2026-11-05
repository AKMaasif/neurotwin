"""Untrusted multi-format parser. Invoked only in a bounded worker subprocess."""

import base64
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from defusedxml import ElementTree as ET

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 100000
MAX_UNITS = 1500
MAX_ASSETS = 20
MAX_CELLS = 20000
MIMES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tif": "image/tiff",
    "tiff": "image/tiff",
}


class Rejected(ValueError):
    pass


def detect(raw, name):
    ext = Path(name).suffix.lower().lstrip(".")
    if ext not in MIMES:
        raise Rejected("unsupported_format")
    if not raw or len(raw) > MAX_BYTES:
        raise Rejected("file_size_limit")
    expected = ext
    if raw.startswith(b"%PDF-"):
        actual = "pdf"
    elif raw.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                infos = z.infolist()
                names = [i.filename for i in infos]
                if (
                    len(infos) > 2000
                    or sum(i.file_size for i in infos) > 50 * 1024 * 1024
                ):
                    raise Rejected("archive_expansion_limit")
                for i in infos:
                    n = i.filename.lower()
                    if (
                        i.flag_bits & 1
                        or ".." in Path(n).parts
                        or n.startswith("/")
                        or ":" in n
                    ):
                        raise Rejected("unsafe_archive")
                    if any(
                        s in n
                        for s in [
                            "vbaproject",
                            "/embeddings/",
                            "activex/",
                            "externallinks/",
                        ]
                    ):
                        raise Rejected("active_content")
                    if (
                        i.file_size > 12 * 1024 * 1024
                        or i.file_size / max(1, i.compress_size) > 250
                    ):
                        raise Rejected("archive_expansion_limit")
                    if n.endswith(".xml") or n.endswith(".rels"):
                        content = z.read(i)
                        if (
                            b"<!DOCTYPE" in content.upper()
                            or b"<!ENTITY" in content.upper()
                        ):
                            raise Rejected("unsafe_xml")
                        if n.endswith(".rels"):
                            tree = ET.fromstring(content)
                            for rel in tree:
                                if rel.attrib.get(
                                    "TargetMode"
                                ) == "External" and not rel.attrib.get(
                                    "Type", ""
                                ).endswith("/hyperlink"):
                                    raise Rejected("external_resource")
                actual = (
                    "docx"
                    if "word/document.xml" in names
                    else "xlsx"
                    if "xl/workbook.xml" in names
                    else "unknown"
                )
        except (zipfile.BadZipFile, ET.ParseError):
            raise Rejected("invalid_container")
    elif raw.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        import olefile

        try:
            with olefile.OleFileIO(io.BytesIO(raw)) as ole:
                paths = ["/".join(p) for p in ole.listdir()]
                if any("vba" in n.lower() or "objectpool" in n.lower() for n in paths):
                    raise Rejected("active_content")
                actual = (
                    "doc"
                    if ole.exists("WordDocument")
                    else "xls"
                    if ole.exists("Workbook") or ole.exists("Book")
                    else "unknown"
                )
                if actual == "doc":
                    head = ole.openstream("WordDocument").read(12)
                    if len(head) < 12 or int.from_bytes(head[10:12], "little") & 0x8100:
                        raise Rejected("encrypted_document")
        except OSError:
            raise Rejected("invalid_container")
    elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
        actual = "png"
    elif raw.startswith(b"\xff\xd8\xff"):
        actual = "jpg"
    elif raw[:4] in [b"II*\x00", b"MM\x00*"]:
        actual = "tif"
    else:
        if b"\x00" in raw and not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise Rejected("binary_text_rejected")
        decode(raw)
        actual = ext if ext in ["txt", "csv"] else "unknown"
    if expected == "jpeg":
        expected = "jpg"
    if expected == "tiff":
        expected = "tif"
    if actual != expected:
        raise Rejected("extension_content_mismatch")
    return actual


def decode(raw):
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeError:
        try:
            return raw.decode("cp1252"), "cp1252"
        except UnicodeError:
            raise Rejected("unknown_encoding")


class Result:
    def __init__(self):
        self.units = []
        self.assets = []
        self.warnings = []
        self.length = 0

    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def unit(self, kind, text, source, **detail):
        text = text.strip()
        self.length += len(text)
        if self.length > MAX_TEXT or len(self.units) >= MAX_UNITS:
            raise Rejected("content_limit")
        if text or detail:
            self.units.append(
                {"kind": kind, "text": text, "source": source, "detail": detail}
            )

    def asset(self, image, source):
        if len(self.assets) >= MAX_ASSETS:
            self.warn("Additional visual assets omitted at the 20-image limit.")
            return
        if image.width * image.height > 20_000_000:
            raise Rejected("image_pixel_limit")
        image = image.convert("RGB")
        image.thumbnail((1800, 1800))
        out = io.BytesIO()
        image.save(out, format="PNG")
        self.assets.append(
            {
                "source": source,
                "data": base64.b64encode(out.getvalue()).decode(),
                "mime": "image/png",
            }
        )

    def finish(self):
        return {
            "units": self.units,
            "assets": self.assets,
            "warnings": self.warnings,
            "text": "\n\n".join(u["text"] for u in self.units if u["text"]),
            "processing_status": "partial"
            if self.warnings or not any(u["text"] for u in self.units)
            else "processed",
        }


def ocr(image, r, source):
    import numpy as np
    from rapidocr import RapidOCR

    # Local models shipped with the pinned RapidOCR wheel, no URLs from documents.
    if not hasattr(ocr, "engine"):
        ocr.engine = RapidOCR(
            params={
                "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )
    result = ocr.engine(np.array(image.convert("RGB")))
    texts = list(result.txts) if result.txts is not None else []
    scores = [float(s) for s in result.scores] if result.scores is not None else []
    boxes = result.boxes.tolist() if result.boxes is not None else []
    if texts:
        score = sum(scores) / len(scores)
        r.unit(
            "ocr",
            "\n".join(texts),
            source,
            method="rapidocr",
            recognition_score=score,
            lines=[
                {"text": t, "score": s, "box": b}
                for t, s, b in zip(texts, scores, boxes)
            ],
            review_required=True,
        )
        if score < 0.85:
            r.warn(
                "Low OCR recognition score; compare transcription with the original image."
            )
    else:
        r.warn(
            "No readable text detected in a visual region; image review is required."
        )
    r.warn(
        "OCR does not establish diagram meaning, handwriting accuracy or clinical correctness."
    )


def parse_pdf(raw, r):
    import pdfplumber
    import pypdfium2 as pdfium
    from pypdf import PdfReader, apply_configuration

    from .pdf_worker import inspect_objects

    apply_configuration(zlib_maximum_output_length=8 * 1024 * 1024)
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise Rejected("encrypted_pdf")
    if not 1 <= len(reader.pages) <= 20:
        raise Rejected("page_limit")
    inspect_objects(reader.trailer["/Root"])
    pdf = pdfium.PdfDocument(raw)
    with pdfplumber.open(io.BytesIO(raw)) as layout:
        for i, page in enumerate(reader.pages):
            loc = {"page": i + 1}
            text = (page.extract_text() or "").strip()
            content = page.get_contents()
            if content is not None and len(content.get_data()) > 4 * 1024 * 1024:
                raise Rejected("content_limit")
            if text:
                r.unit("paragraph", text, loc, method="pypdf")
            for ti, table in enumerate(layout.pages[i].extract_tables()):
                rows = [[str(c or "") for c in row] for row in table]
                r.unit(
                    "table",
                    "\n".join(" | ".join(row) for row in rows),
                    loc | {"table": ti + 1},
                    rows=rows,
                    method="pdfplumber",
                    review_required=True,
                )
            has_images = bool(layout.pages[i].images)
            if has_images or not text:
                image = (
                    pdf[i].render(scale=min(2, 1800 / max(pdf[i].get_size()))).to_pil()
                )
                r.asset(image, loc | {"visual": "page"})
                if not text:
                    ocr(image, r, loc)
                else:
                    # OCR each raster region: text elsewhere on a page must not hide a scan.
                    for ii, item in enumerate(layout.pages[i].images[:10]):
                        bbox = (
                            max(0, item["x0"]),
                            max(0, item["top"]),
                            min(layout.pages[i].width, item["x1"]),
                            min(layout.pages[i].height, item["bottom"]),
                        )
                        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                            continue
                        sx = image.width / layout.pages[i].width
                        sy = image.height / layout.pages[i].height
                        crop = image.crop(
                            (
                                int(bbox[0] * sx),
                                int(bbox[1] * sy),
                                int(bbox[2] * sx),
                                int(bbox[3] * sy),
                            )
                        )
                        ocr(crop, r, loc | {"image": ii + 1})
            # Vector diagrams are preserved in the original even when native text exists.
            if layout.pages[i].curves and not has_images:
                r.asset(
                    pdf[i].render(scale=1.5).to_pil(), loc | {"visual": "vector_page"}
                )
                r.warn(
                    "Vector graphics detected; their relationships require visual review."
                )
    pdf.close()


def parse_docx(raw, r):
    from docx import Document
    from docx.table import Table

    doc = Document(io.BytesIO(raw))
    section = "Document"
    paragraph = 0
    table = 0
    media_locations = {}
    for block in doc.iter_inner_content():
        if isinstance(block, Table):
            table += 1
            rows = [[c.text for c in row.cells] for row in block.rows]
            location = {"section": section, "table": table}
            r.unit(
                "table",
                "\n".join(" | ".join(row) for row in rows),
                location,
                rows=rows,
                method="python-docx",
            )
        else:
            paragraph += 1
            if block.style and block.style.name.startswith("Heading"):
                section = block.text
            location = {"section": section, "paragraph": paragraph}
            if block.text:
                r.unit(
                    "heading"
                    if block.style and block.style.name.startswith("Heading")
                    else "paragraph",
                    block.text,
                    location,
                    method="python-docx",
                )
        for blip in block._element.xpath(".//a:blip"):
            rel = blip.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            )
            if rel and rel in doc.part.rels:
                part = doc.part.rels[rel].target_part
                media_locations[str(part.partname).lstrip("/")] = location
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            if name.startswith("word/media/"):
                from PIL import Image

                try:
                    image = Image.open(io.BytesIO(z.read(name)))
                    image.load()
                    loc = media_locations.get(name, {}) | {"image": name}
                    r.asset(image, loc)
                    ocr(image, r, loc)
                except (OSError, ValueError):
                    r.warn("An embedded image format needs original-document review.")
            elif name.startswith("word/charts/") and name.endswith(".xml"):
                root = ET.fromstring(z.read(name))
                labels = [
                    e.text for e in root.iter() if e.tag.endswith("}v") and e.text
                ]
                r.unit(
                    "chart",
                    " | ".join(labels),
                    {"chart": name},
                    method="chart_xml",
                    review_required=True,
                )
                r.warn(
                    "Chart XML labels/values preserve cached order only; visual relationships need review."
                )
        xml = z.read("word/document.xml")
        if b"<w:drawing" in xml:
            r.warn(
                "Embedded drawings may contain relationships not represented by OCR text."
            )
        if b"<w:ins " in xml or b"<w:del " in xml:
            r.warn("Tracked changes detected; inspect the original revision markup.")
        for name in z.namelist():
            if re.match(r"word/(header|footer|footnotes|endnotes).*\.xml$", name):
                content = " ".join(
                    e.text
                    for e in ET.fromstring(z.read(name)).iter()
                    if e.tag.endswith("}t") and e.text
                )
                if content:
                    r.unit(
                        "paragraph",
                        content,
                        {"section": name},
                        method="ooxml_auxiliary",
                    )


def parse_xlsx(raw, r):
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    a = load_workbook(
        io.BytesIO(raw), read_only=False, data_only=False, keep_links=False
    )
    b = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
    cells = 0
    media_locations = {}
    if len(a.worksheets) > 20:
        raise Rejected("worksheet_limit")
    for ws in a.worksheets:
        if ws.max_row > 2000 or ws.max_column > 100:
            raise Rejected("worksheet_dimensions_limit")
        merged = [str(x) for x in ws.merged_cells.ranges]
        for image in ws._images:
            anchor = getattr(image.anchor, "_from", None)
            if anchor is not None:
                media_locations[hashlib.sha256(image._data()).hexdigest()] = {
                    "worksheet": ws.title,
                    "cell": f"{get_column_letter(anchor.col + 1)}{anchor.row + 1}",
                }
        for row in ws.iter_rows():
            values = []
            formulas = {}
            for c in row:
                cells += 1
                if cells > MAX_CELLS:
                    raise Rejected("cell_limit")
                v = c.value
                if c.data_type == "f":
                    cached = b[ws.title][c.coordinate].value
                    formulas[c.coordinate] = {"formula": v, "cached_value": cached}
                    v = cached
                    if cached is None:
                        r.warn(
                            "Formula cached values are missing; formulas are preserved but never calculated."
                        )
                values.append("" if v is None else str(v))
            if any(values) or formulas:
                n = row[0].row
                refs = [f"{get_column_letter(i + 1)}{n}" for i in range(len(values))]
                text = " | ".join(f"{ref}: {value}" for ref, value in zip(refs, values))
                r.unit(
                    "row",
                    text,
                    {"worksheet": ws.title, "row": n, "range": f"A{n}:{refs[-1]}"},
                    values=values,
                    cell_references=refs,
                    formulas=formulas,
                    merged_ranges=merged,
                    method="openpyxl",
                )
    a.close()
    b.close()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            if name.startswith("xl/media/"):
                from PIL import Image

                try:
                    data = z.read(name)
                    im = Image.open(io.BytesIO(data))
                    im.load()
                    loc = media_locations.get(hashlib.sha256(data).hexdigest(), {}) | {
                        "image": name
                    }
                    r.asset(im, loc)
                    ocr(im, r, loc)
                except (OSError, ValueError):
                    r.warn("Workbook embedded image needs original review.")
            elif name.startswith("xl/charts/") and name.endswith(".xml"):
                labels = [
                    e.text
                    for e in ET.fromstring(z.read(name)).iter()
                    if e.tag.endswith("}v") and e.text
                ]
                r.unit(
                    "chart",
                    " | ".join(labels),
                    {"chart": name},
                    method="chart_xml",
                    review_required=True,
                )
                r.warn("Workbook chart semantics require visual review.")


def parse_xls(raw, r):
    import xlrd
    from openpyxl.utils import get_column_letter

    book = xlrd.open_workbook(file_contents=raw, formatting_info=True, on_demand=True)
    count = 0
    if book.nsheets > 20:
        raise Rejected("worksheet_limit")
    for sheet in book.sheets():
        if sheet.nrows > 2000 or sheet.ncols > 100:
            raise Rejected("worksheet_dimensions_limit")
        for n in range(sheet.nrows):
            values = []
            for c in range(sheet.ncols):
                count += 1
                if count > MAX_CELLS:
                    raise Rejected("cell_limit")
                cell = sheet.cell(n, c)
                value = (
                    xlrd.xldate.xldate_as_datetime(
                        cell.value, book.datemode
                    ).isoformat()
                    if cell.ctype == xlrd.XL_CELL_DATE
                    else str(cell.value)
                    if cell.ctype
                    else ""
                )
                values.append(value)
            refs = [f"{get_column_letter(i + 1)}{n + 1}" for i in range(len(values))]
            if any(values):
                r.unit(
                    "row",
                    " | ".join(f"{ref}: {v}" for ref, v in zip(refs, values)),
                    {
                        "worksheet": sheet.name,
                        "row": n + 1,
                        "range": f"A{n + 1}:{refs[-1]}",
                    },
                    values=values,
                    cell_references=refs,
                    merged_ranges=sheet.merged_cells,
                    method="xlrd",
                )
    r.warn(
        "Legacy XLS exposes stored cell results; formula expressions and embedded visuals require original review."
    )
    book.release_resources()


def soffice_path():
    import shutil

    options = [
        os.environ.get("DOCUMENT_SOFFICE", ""),
        r"C:\Program Files\LibreOffice\program\soffice.com",
        str(
            Path(__file__).resolve().parents[1]
            / "data/tools/libreoffice/program/soffice.com"
        ),
    ]
    return next((p for p in options if p and Path(p).is_file()), None) or shutil.which(
        "soffice"
    )


def parse_doc(raw, r):
    exe = soffice_path()
    if not exe:
        raise Rejected("legacy_word_runtime_missing")
    with tempfile.TemporaryDirectory(prefix="nt-doc-") as d:
        folder = Path(d)
        (folder / "input.doc").write_bytes(raw)
        profile = folder / "profile"
        profile.mkdir()
        # Disable macros at the highest security level in a disposable, non-interactive profile.
        user = profile / "user"
        user.mkdir()
        (user / "registrymodifications.xcu").write_text(
            '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item></oor:items>',
            encoding="utf-8",
        )
        subprocess.run(
            [
                exe,
                "-env:UserInstallation=" + profile.as_uri(),
                "--headless",
                "--nologo",
                "--nodefault",
                "--norestore",
                "--convert-to",
                "docx",
                "--outdir",
                d,
                str(folder / "input.doc"),
            ],
            timeout=35,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            check=True,
        )
        converted = (folder / "input.docx").read_bytes()
        detect(converted, "converted.docx")
        parse_docx(converted, r)
        r.warn(
            "Legacy Word was converted; section references refer to converted structure, not original page numbers."
        )


def parse(raw, name):
    from PIL import Image, ImageSequence

    Image.MAX_IMAGE_PIXELS = 20_000_000
    fmt = detect(raw, name)
    r = Result()
    if fmt == "pdf":
        parse_pdf(raw, r)
    elif fmt == "docx":
        parse_docx(raw, r)
    elif fmt == "xlsx":
        parse_xlsx(raw, r)
    elif fmt == "xls":
        parse_xls(raw, r)
    elif fmt == "doc":
        parse_doc(raw, r)
    elif fmt in ["txt", "csv"]:
        text, encoding = decode(raw)
        if len(text) > MAX_TEXT:
            raise Rejected("content_limit")
        if encoding == "cp1252":
            r.warn("Encoding inferred as Windows-1252; verify accented characters.")
        if fmt == "txt":
            for i, p in enumerate(re.split(r"\n\s*\n", text), 1):
                r.unit(
                    "paragraph", p, {"paragraph": i}, method="text", encoding=encoding
                )
        else:
            try:
                delimiter = (
                    csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
                )
            except csv.Error:
                delimiter = ","
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
            if len(rows) > 2000 or any(len(row) > 100 for row in rows):
                raise Rejected("csv_dimensions_limit")
            headers = rows[0] if rows else []
            for i, row in enumerate(rows, 1):
                if len(row) != len(headers):
                    r.warn(
                        "Inconsistent CSV row widths; missing/extra cells are preserved."
                    )
                r.unit(
                    "row",
                    " | ".join(
                        f"{headers[c] if c < len(headers) else 'column ' + str(c + 1)}: {v}"
                        for c, v in enumerate(row)
                    ),
                    {"row": i, "columns": list(range(1, len(row) + 1))},
                    values=row,
                    headers=headers,
                    delimiter=delimiter,
                    encoding=encoding,
                    method="csv",
                )
    else:
        im = Image.open(io.BytesIO(raw))
        if getattr(im, "n_frames", 1) > 20:
            raise Rejected("image_frame_limit")
        for i, frame in enumerate(ImageSequence.Iterator(im), 1):
            frame.load()
            image = frame.copy()
            r.asset(image, {"page": i, "image": "uploaded"})
            ocr(image, r, {"page": i, "image": "uploaded"})
    return r.finish() | {"format": fmt, "mime": MIMES[fmt]}


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        result = parse(raw, sys.argv[1])
        body = {"ok": True, "result": result}
    except Rejected as exc:
        body = {"ok": False, "reason": str(exc)}
    except Exception:
        body = {"ok": False, "reason": "unreadable_document"}
    sys.stdout.buffer.write(
        json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
    )


if __name__ == "__main__":
    main()
