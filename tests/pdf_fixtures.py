"""Small in-memory fictional PDF fixtures, with no external assets or clinical items."""

import io

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    TextStringObject,
)


def make_pdf(lines=None, pages=1, encrypted=False, javascript=False):
    writer = PdfWriter()
    for i in range(pages):
        page = writer.add_blank_page(width=595, height=842)
        if lines:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            source = lines[i] if isinstance(lines, list) else lines
            safe = source.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 16 Tf 50 750 Td ({safe}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("fictional-password")
    if javascript:
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
            {
                NameObject("/S"): NameObject("/JavaScript"),
                NameObject("/JS"): TextStringObject("fixture"),
            }
        )
    data = io.BytesIO()
    writer.write(data)
    return data.getvalue()
