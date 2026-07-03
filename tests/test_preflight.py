from pathlib import Path
from preflight import check


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_unset_data_root_not_ready():
    r = check(None)
    assert r["ready"] is False
    assert any("data_root_unset" in i for i in r["issues"])
    assert isinstance(r["suggested_data_root"], list)


def test_missing_folder_flagged():
    r = check("/no/such/folder/xyz123")
    assert r["ready"] is False
    assert any("data_root_missing" in i for i in r["issues"])


def test_folder_with_no_cycling_files_flagged(tmp_path):
    (tmp_path / "readme.txt").write_text("x")
    r = check(str(tmp_path))
    assert r["ready"] is False
    assert any("no_cycling_files" in i for i in r["issues"])


def test_valid_data_root_ready(tmp_path):
    # deps (pandas/numpy/matplotlib/scipy) are installed in the test env
    _touch(tmp_path / "1Cycler" / "06.26" / "260601" / "260601_Si100_Test4_DOE1_25.csv")
    r = check(str(tmp_path))
    assert r["ready"] is True
    assert r["issues"] == []
