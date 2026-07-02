from pathlib import Path
from run_analysis import run

def test_run_on_sample_data(sample_data_dir, tmp_path):
    result = run(sample_data_dir, tmp_path / "out", tmp_path / "work")
    assert "Test4" in result["tests"] or "Test5" in result["tests"]
    # produced at least one CSV summary and the config was generated
    assert result["csvs"], "expected summary CSVs"
    assert (Path(__file__).resolve().parent.parent / "engine" / "config.py").exists()
