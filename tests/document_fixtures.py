"""Fictional format fixtures for parser and pipeline acceptance tests."""

import io

from docx import Document
from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter


def image_bytes(fmt="PNG"):
    for name in ["Arial.ttf", "DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]:
        try:
            font = ImageFont.truetype(name, 36)
            break
        except OSError:
            continue
    else:
        font = ImageFont.load_default(size=36)
    im = Image.new("RGB", (1000, 250), "white")
    ImageDraw.Draw(im).text(
        (35, 65),
        "Appointment date: 2026-11-18",
        font=font,
        fill="black",
    )
    o = io.BytesIO()
    im.save(o, format=fmt)
    return o.getvalue()


def docx_bytes(images=False):
    d = Document()
    d.add_heading("Fictional appointment", level=1)
    d.add_paragraph("Transport assistance requested.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Activity"
    t.cell(0, 1).text = "Date"
    t.cell(1, 0).text = "Appointment"
    t.cell(1, 1).text = "2026-11-18"
    if images:
        d.add_picture(io.BytesIO(image_bytes()))
    o = io.BytesIO()
    d.save(o)
    return o.getvalue()


def xlsx_bytes():
    b = Workbook()
    s = b.active
    s.title = "Appointments"
    s.append(["Activity", "Date"])
    s.append(["Transport", "2026-11-18"])
    s["C2"] = "=1+2"
    s.merge_cells("A4:B4")
    s["A4"] = "Fictional merged note"
    b.create_sheet("Support").append(["Family", "Phone"])
    o = io.BytesIO()
    b.save(o)
    return o.getvalue()


def xls_bytes():
    import xlwt

    b = xlwt.Workbook()
    s = b.add_sheet("Appointments")
    s.write(0, 0, "Transport assistance")
    s.write(1, 0, "2026-11-18")
    o = io.BytesIO()
    b.save(o)
    return o.getvalue()


def scanned_pdf(mixed=False):
    image = Image.open(io.BytesIO(image_bytes()))
    o = io.BytesIO()
    image.save(o, format="PDF")
    scan = o.getvalue()
    if not mixed:
        return scan
    from pdf_fixtures import make_pdf

    w = PdfWriter()
    w.append(PdfReader(io.BytesIO(make_pdf("Fictional selectable source"))))
    w.append(PdfReader(io.BytesIO(scan)))
    o = io.BytesIO()
    w.write(o)
    return o.getvalue()
