"""Bounded subprocess PDF parsing. JSON protocol only; no filenames or credentials."""

import io
import json
import sys

from pypdf import PdfReader, apply_configuration
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 10
MAX_TEXT = 12000
FORBIDDEN_KEYS = {
    "/OpenAction",
    "/AA",
    "/JavaScript",
    "/JS",
    "/EmbeddedFiles",
    "/RichMediaContent",
    "/XFA",
}
FORBIDDEN_ACTIONS = {
    "/JavaScript",
    "/Launch",
    "/SubmitForm",
    "/ImportData",
    "/GoToR",
    "/Rendition",
    "/RichMediaExecute",
}


class Rejected(ValueError):
    pass


def inspect_objects(root):
    stack = [root]
    seen = set()
    count = 0
    while stack:
        obj = stack.pop()
        count += 1
        if count > 20000:
            raise Rejected("object_limit")
        if isinstance(obj, IndirectObject):
            key = (obj.idnum, obj.generation)
            if key in seen:
                continue
            seen.add(key)
            obj = obj.get_object()
        if isinstance(obj, DictionaryObject):
            if any(k in obj for k in FORBIDDEN_KEYS):
                raise Rejected("active_content")
            if str(obj.get("/S", "")) in FORBIDDEN_ACTIONS:
                raise Rejected("active_content")
            if str(obj.get("/Type", "")) == "/Filespec" and "/EF" in obj:
                raise Rejected("embedded_file")
            stack.extend(obj.values())
        elif isinstance(obj, ArrayObject):
            stack.extend(obj)


def parse(data):
    if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
        raise Rejected("invalid_pdf")
    # Library-level decompression guard plus subprocess timeout. Not an OS sandbox.
    apply_configuration(zlib_maximum_output_length=8 * 1024 * 1024)
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise Rejected("encrypted_pdf")
    if not 1 <= len(reader.pages) <= MAX_PAGES:
        raise Rejected("page_limit")
    inspect_objects(reader.trailer["/Root"])
    pages = []
    length = 0
    for i, page in enumerate(reader.pages, 1):
        content = page.get_contents()
        if content is not None and len(content.get_data()) > 4 * 1024 * 1024:
            raise Rejected("content_limit")
        text = (page.extract_text() or "").strip()
        length += len(text)
        if length > MAX_TEXT:
            raise Rejected("text_limit")
        pages.append(
            {
                "number": i,
                "text": text,
                "text_status": "extracted" if text else "no_extractable_text",
            }
        )
    return {
        "pages": pages,
        "page_count": len(pages),
        "text": "\n\n".join(p["text"] for p in pages),
        "status": "ocr_required"
        if any(not p["text"] for p in pages)
        else "awaiting_extraction",
    }


def main():
    try:
        result = {"ok": True, "result": parse(sys.stdin.buffer.read(MAX_BYTES + 1))}
    except Rejected as exc:
        result = {"ok": False, "reason": str(exc)}
    except Exception:
        result = {"ok": False, "reason": "unreadable_pdf"}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
