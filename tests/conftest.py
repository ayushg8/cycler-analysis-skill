from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture
def sample_data_dir():
    d = ROOT / "data"
    if not any(d.glob("*.csv")):
        pytest.skip("sample CSVs not present in data/")
    return d
