import io
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import oasis2_extract as X  # noqa: E402


def make(tmp_path):
    path = tmp_path / "a.tar.gz"
    names = ["OAS2_RAW_PART1/OAS2_0001_MR1/RAW/mpr-1.nifti.hdr", "OAS2_RAW_PART1/OAS2_0001_MR1/RAW/mpr-1.nifti.img",
             "OAS2_RAW_PART1/OAS2_0001_MR1/RAW/mpr-2.nifti.img", "OAS2_RAW_PART1/OAS2_0001_MR1/OLD/x",
             "OAS2_RAW_PART1/OAS2_0002_MR1/RAW/mpr-1.nifti.hdr", "OAS2_RAW_PART1/OAS2_0003_MR1/RAW/mpr-1.nifti.hdr"]
    with tarfile.open(path, "w:gz") as t:
        for n in names:
            data = b"x" * 5; info = tarfile.TarInfo(n); info.size = len(data); t.addfile(info, io.BytesIO(data))
    return path


def test_only_requested_subjects_and_scans_are_written(tmp_path):
    n = X.extract(make(tmp_path), {"OAS2_0001"}, tmp_path / "out", {"mpr-1"})
    got = sorted(p.name for p in (tmp_path / "out").rglob("*") if p.is_file())
    assert n == 2 and got == ["mpr-1.nifti.hdr", "mpr-1.nifti.img"]


def test_stops_after_the_last_requested_subject(tmp_path):
    n = X.extract(make(tmp_path), {"OAS2_0001", "OAS2_0002"}, tmp_path / "out", {"mpr-1"})
    assert n == 3 and not list((tmp_path / "out").rglob("OAS2_0003*"))
