import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("IBC_DATA_DIR", _ROOT / "data"))
OUT_DIR = Path(os.environ.get("IBC_OUT_DIR", _ROOT / "output"))
