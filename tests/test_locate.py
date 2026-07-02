from pathlib import Path
from locate import is_cycling_file, find_cycling_csvs, latest_day_dir

def test_is_cycling_file_selects_plain_and_skips_protocol():
    assert is_cycling_file("260601_Si100_Test4_DOE1_25.csv") is True
    assert is_cycling_file("260526_Si100_Test3_DOE4_45.csv") is True
    assert is_cycling_file("260526_Si100_Test1_OCV_DOE8_25.csv") is False
    assert is_cycling_file("260626_Si100_Test1_3C_HPPC_DisCharge_DOE1_25.csv") is False
    assert is_cycling_file("notes.txt") is False

def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text("x")

def test_find_recurses_cycler_month_day(tmp_path):
    # mimic 1Cycler/06.26/260601 and a characterization file that must be skipped
    _touch(tmp_path / "1Cycler" / "06.26" / "260601" / "260601_Si100_Test4_DOE1_25.csv")
    _touch(tmp_path / "1Cycler" / "06.26" / "260601" / "260526_Si100_Test1_OCV_DOE8_25.csv")
    _touch(tmp_path / "2Cycler" / "06.26" / "260601" / "260601_Si100_Test5_DOE4_45.csv")
    _touch(tmp_path / "Run 8" / "junk.csv")
    got = {p.name for p in find_cycling_csvs(tmp_path)}
    assert got == {"260601_Si100_Test4_DOE1_25.csv", "260601_Si100_Test5_DOE4_45.csv"}

def test_latest_day_dir(tmp_path):
    _touch(tmp_path / "1Cycler" / "06.26" / "260601" / "260601_Si100_Test4_DOE1_25.csv")
    _touch(tmp_path / "1Cycler" / "06.26" / "260629" / "260629_Si100_Test4_DOE1_25.csv")
    assert latest_day_dir(tmp_path).name == "260629"
