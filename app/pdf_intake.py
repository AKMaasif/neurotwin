import json
import os
import subprocess
import sys
import threading

from .config import ROOT

_slots = threading.BoundedSemaphore(2)


class PDFRejected(ValueError):
    pass


def parse_pdf(data):
    if not _slots.acquire(blocking=False):
        raise PDFRejected("parser_busy")
    try:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "app.pdf_worker"],
                input=data,
                capture_output=True,
                timeout=15,
                cwd=ROOT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                env={
                    k: v
                    for k, v in os.environ.items()
                    if not any(
                        s in k.upper()
                        for s in ["KEY", "TOKEN", "PASSWORD", "DATABASE_URL"]
                    )
                },
            )
        except subprocess.TimeoutExpired:
            raise PDFRejected("parser_timeout")
        if result.returncode or len(result.stdout) > 100000:
            raise PDFRejected("parser_failed")
        body = json.loads(result.stdout.decode("utf-8"))
        if not body.get("ok"):
            raise PDFRejected(body.get("reason", "unreadable_pdf"))
        return body["result"]
    except (UnicodeError, json.JSONDecodeError):
        raise PDFRejected("parser_failed")
    finally:
        _slots.release()
