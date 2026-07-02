from __future__ import annotations
import argparse
import os
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_ENGINE = _ROOT / "engine"
sys.path.insert(0, str(_ENGINE))

from locate import find_cycling_csvs  # noqa: E402


def _flatten(data_root: Path, work_data: Path) -> int:
    """Copy the cycling CSVs found under data_root into one flat work dir."""
    work_data.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in find_cycling_csvs(data_root):
        dest = work_data / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
            n += 1
    return n


def run(data_root: Path, out_dir: Path, work_dir: Path) -> dict:
    data_root, out_dir, work_dir = Path(data_root), Path(out_dir), Path(work_dir)
    work_data = work_dir / "data"
    n = _flatten(data_root, work_data)

    # Point the engine at the flattened data + chosen output dir
    os.environ["IBC_DATA_DIR"] = str(work_data)
    os.environ["IBC_OUT_DIR"] = str(out_dir)

    import importlib
    import paths; importlib.reload(paths)          # re-read env
    from discover import discover, build_config
    from configgen import write_config
    cfg = build_config(discover(work_data), {})
    write_config(cfg, _ENGINE / "config.py")

    import run_all; importlib.reload(run_all)
    run_all.main()

    plots = sorted(str(p) for p in out_dir.rglob("*.png"))
    csvs = sorted(str(p) for p in out_dir.rglob("*.csv"))
    return {
        "tests": list(cfg["tests"].keys()),
        "does": list(cfg["runs"].keys()),
        "files_ingested": n,
        "plots": plots,
        "csvs": csvs,
        "summary": (f"{len(cfg['tests'])} tests, {len(cfg['runs'])} DOEs, "
                    f"{len(plots)} plots, {len(csvs)} CSVs"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cycler-analysis")
    ap.add_argument("--data", required=True, help="folder to search for cycling CSVs")
    ap.add_argument("--out", default=str(_ROOT / "output"), help="results folder")
    ap.add_argument("--work", default=str(_ROOT / "work"), help="scratch folder")
    args = ap.parse_args(argv)
    result = run(Path(args.data), Path(args.out), Path(args.work))
    print(result["summary"])
    for p in result["plots"]:
        print("plot:", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
