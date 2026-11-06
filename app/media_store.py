"""Private local object adapter. Keys, never filenames, determine storage paths."""

import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException

from .config import ROOT, settings


def object_path(key):
    root = Path(settings.media_store_path).resolve()
    if root == (ROOT / "web").resolve() or (ROOT / "web").resolve() in root.parents:
        raise RuntimeError("Media storage must be outside the public web root")
    if not re.fullmatch(r"[a-z0-9][a-z0-9/._-]{0,249}", key) or any(
        p in {"", ".", ".."} for p in key.split("/")
    ):
        raise HTTPException(400, "Invalid object key")
    target = (root / key).resolve()
    if root not in target.parents:
        raise HTTPException(400, "Invalid object key")
    return target


def write_object(key, data):
    target = object_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return target


def delete_object(key):
    if key:
        object_path(key).unlink(missing_ok=True)
