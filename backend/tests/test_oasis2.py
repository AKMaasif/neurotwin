import pytest

openpyxl = pytest.importorskip("openpyxl")

from app import oasis2

HEAD = ["Subject ID", "MRI ID", "Group", "Visit", "MR Delay", "M/F", "Hand", "Age", "EDUC", "SES", "MMSE", "CDR", "eTIV", "nWBV", "ASF"]


@pytest.fixture
def table(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(HEAD)
    ws.append(["OAS2_0001", "OAS2_0001_MR2", "Nondemented", "=RIGHT(B3,1)", 457, "M", "R", 88, 14, 2, 30, 0, 2004.4, 0.68, 0.87])  # out of order on purpose
    ws.append(["OAS2_0001", "OAS2_0001_MR1", "Nondemented", "=RIGHT(B2,1)", 0, "M", "R", 87, 14, 2, 27, 0, 1986.5, 0.69, 0.88])
    ws.append(["OAS2_0002", "OAS2_0002_MR1", "Demented", "=RIGHT(B4,1)", 0, "F", "R", 75, 12, None, None, 0.5, 1678.2, 0.73, 1.04])
    ws.append(["OAS2_0002", "OAS2_0002_MR2", "Demented", "=RIGHT(B5,1)", 560, "F", "R", 76, 12, None, 28, 0.5, 1737.6, 0.71, 1.01])
    ws.append(["OAS2_0002", "OAS2_0002_MR3", "Demented", "=RIGHT(B6,1)", 1895, "F", "R", 80, 12, None, 22, 0.5, 1697.9, 0.70, 1.03])
    path = tmp_path / "Demographic Data.xlsx"; wb.save(path)
    return path


def listing(*items):
    return [f"-rw-r----- u/g {size} 2009-03-18 15:28 OAS2_RAW_PART1/{p}" for p, size in items]


GOOD = [("OAS2_0001_MR1/RAW/mpr-1.nifti.hdr", 348), ("OAS2_0001_MR1/RAW/mpr-1.nifti.img", 33554432),
        ("OAS2_0001_MR2/RAW/mpr-1.nifti.hdr", 348), ("OAS2_0001_MR2/RAW/mpr-1.nifti.img", 33554432),
        ("OAS2_0002_MR1/RAW/mpr-1.nifti.hdr", 348), ("OAS2_0002_MR1/RAW/mpr-1.nifti.img", 33554432)]


def build(table, items):
    scans = oasis2.index_scans(oasis2.parse_listing(listing(*items)))
    return oasis2.build_manifest(oasis2.load_table(table), scans), scans


def test_order_and_gaps_come_from_mr_delay_not_the_visit_formula(table):
    manifest, _ = build(table, GOOD)
    visits = manifest["subjects"][0]["visits"]
    assert [v["mri_id"] for v in visits] == ["OAS2_0001_MR1", "OAS2_0001_MR2"]
    assert visits[0]["years_since_previous"] is None and visits[1]["years_since_previous"] == round(457 / 365.25, 3)


def test_missing_values_stay_missing_and_group_is_only_a_label(table):
    manifest, _ = build(table, GOOD)
    s2 = manifest["subjects"][1]
    assert s2["visits"][0]["clinical"]["MMSE"] is None and s2["visits"][0]["clinical"]["SES"] is None
    assert s2["group_label_from_dataset"] == "Demented"
    assert "Group" not in s2["visits"][0]["clinical"]


def test_visits_without_scans_are_named_not_dropped(table):
    manifest, _ = build(table, GOOD)
    s2 = manifest["subjects"][1]
    assert [v["status"] for v in s2["visits"]] == ["usable", "no_scan_in_archives", "no_scan_in_archives"]
    assert manifest["summary"]["visits_without_scan"] == 2
    assert s2["level1_compare"] is False and s2["level2_trend"] is False


def test_level_eligibility_counts_usable_visits_only(table):
    manifest, _ = build(table, GOOD)
    assert manifest["subjects"][0]["level1_compare"] is True
    assert manifest["subjects"][0]["level2_trend"] is False  # two visits cannot give a trend
    assert manifest["summary"]["level1_subjects"] == 1


def test_a_bad_header_or_missing_image_makes_the_scan_unusable_with_a_reason(table):
    items = [("OAS2_0001_MR1/RAW/mpr-1.nifti.hdr", 100), ("OAS2_0001_MR1/RAW/mpr-1.nifti.img", 5),
             ("OAS2_0001_MR2/RAW/mpr-1.nifti.hdr", 348)]
    manifest, _ = build(table, items)
    v1, v2 = manifest["subjects"][0]["visits"]
    assert v1["status"] == "unusable" and "348" in v1["problems"][0]
    assert v2["status"] == "unusable" and "missing" in v2["problems"][0]


def test_a_second_good_repeat_rescues_a_visit_with_one_bad_repeat(table):
    items = GOOD + [("OAS2_0001_MR1/RAW/mpr-2.nifti.hdr", 100), ("OAS2_0001_MR1/RAW/mpr-2.nifti.img", 10)]
    manifest, _ = build(table, items)
    v1 = manifest["subjects"][0]["visits"][0]
    assert v1["status"] == "usable" and v1["usable_scans"] == ["mpr-1"] and v1["problems"]


def test_archive_visits_missing_from_the_table_are_reported(table):
    manifest, _ = build(table, GOOD + [("OAS2_0999_MR1/RAW/mpr-1.nifti.hdr", 348)])
    assert manifest["archive_visits_not_in_table"] == ["OAS2_0999_MR1"]


def test_imported_measures_are_labelled_separately(table):
    manifest, _ = build(table, GOOD)
    assert set(manifest["subjects"][0]["visits"][0]["imported_measures"]) == {"eTIV", "nWBV", "ASF"}


def test_listing_parser_ignores_directories_and_garbage():
    lines = ["drwxr-x--- u/g 0 2009-03-18 15:28 OAS2_RAW_PART1/OAS2_0001_MR1/", "not a listing line",
             "-rw-r----- u/g 348 2009-03-18 15:28 OAS2_RAW_PART1/OAS2_0001_MR1/RAW/mpr-1.nifti.hdr"]
    assert oasis2.parse_listing(lines) == [("OAS2_RAW_PART1/OAS2_0001_MR1/RAW/mpr-1.nifti.hdr", 348)]


def test_bsdtar_listing_format_and_utf16_are_read(tmp_path):
    lines = ["drwxr-xr-x  0 u g 0 Mar 18  2009 OAS2_RAW_PART1/",
             "-rw-r-----  0 dmarcus wheel 348 Mar 18  2009 OAS2_RAW_PART1/OAS2_0001_MR1/RAW/mpr-1.nifti.hdr",
             "-rw-r-----  0 dmarcus wheel 273 Mar 18  2009 OAS2_RAW_PART1/OAS2_0001_MR1/OLD/mpr-3_to_711-2C_t4"]
    path = tmp_path / "list.txt"; path.write_bytes("\n".join(lines).encode("utf-16"))
    files = oasis2.parse_listing(oasis2.read_listing(path))
    assert files[0] == ("OAS2_RAW_PART1/OAS2_0001_MR1/RAW/mpr-1.nifti.hdr", 348) and len(files) == 2
    assert list(oasis2.index_scans(files)) == ["OAS2_0001_MR1"]  # files outside RAW/ are not scans
