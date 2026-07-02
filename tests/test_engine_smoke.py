import importlib, sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"

def test_engine_imports():
    sys.path.insert(0, str(ENGINE))
    import extract, discover, configgen, paths  # noqa: F401
    from discover import parse_filename
    assert parse_filename("260601_Si100_Test4_DOE1_25.csv")["test"] == "Test4"
