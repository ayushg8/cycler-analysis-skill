"""First-run setup check for the cycler-analysis skill.

Reports whether the machine is ready to run: dependencies installed, and a
DATA_ROOT that exists and actually contains cycling files. When DATA_ROOT is
not set yet, it looks for a "Cycler data" folder in the usual Google Drive for
Desktop mount points and suggests it, so setup is one confirmation.
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from locate import find_cycling_csvs  # noqa: E402

_REQUIRED = ["pandas", "numpy", "matplotlib", "scipy"]


def _drive_candidates() -> list[Path]:
    """Standard Google Drive for Desktop locations that may hold 'Cycler data'."""
    home = Path.home()
    roots: list[Path] = []
    cloud = home / "Library" / "CloudStorage"          # macOS Drive for Desktop
    if cloud.exists():
        for gd in cloud.glob("GoogleDrive-*"):
            roots.append(gd / "Shared drives")
            roots.append(gd / "My Drive")
    roots.append(Path("/Volumes/GoogleDrive/Shared drives"))   # legacy macOS
    for letter in "GHIJKLMN":                                   # Windows drive letters
        roots.append(Path(letter + ":/Shared drives"))
    found: list[Path] = []
    for r in roots:
        try:
            if r.exists():
                for sub in r.iterdir():
                    if sub.is_dir() and "cycler" in sub.name.lower():
                        found.append(sub)
        except OSError:
            continue
    return found


def check(data_root: str | None) -> dict:
    issues: list[str] = []

    missing = [m for m in _REQUIRED if importlib.util.find_spec(m) is None]
    if missing:
        issues.append("missing_deps: " + ", ".join(missing))

    data_ok = False
    if data_root:
        p = Path(data_root).expanduser()
        if not p.exists():
            issues.append("data_root_missing: " + str(p))
        elif not find_cycling_csvs(p):
            issues.append("no_cycling_files under: " + str(p))
        else:
            data_ok = True
    else:
        issues.append("data_root_unset")

    suggestions = [str(c) for c in _drive_candidates()] if not data_ok else []
    return {"ready": not issues, "issues": issues, "suggested_data_root": suggestions}


def main() -> int:
    import settings
    result = check(settings.DATA_ROOT or None)
    if result["ready"]:
        print("READY")
        return 0
    print("SETUP NEEDED:")
    for i in result["issues"]:
        print("  - " + i)
    if result["suggested_data_root"]:
        print("Candidate Cycler data folders (set DATA_ROOT in settings.py to one):")
        for s in result["suggested_data_root"]:
            print("  " + s)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
