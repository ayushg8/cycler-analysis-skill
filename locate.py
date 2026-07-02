from __future__ import annotations
import re
from pathlib import Path

# Plain cycling name: Test<N> directly adjacent to DOE<M>, no protocol token between.
_CYCLING = re.compile(
    r"^\d{6}_[A-Za-z0-9]+_Test\d+_DOE\d+_\d+\.csv$", re.IGNORECASE
)
_DAY = re.compile(r"^\d{6}$")  # YYMMDD day folder


def is_cycling_file(name: str) -> bool:
    return bool(_CYCLING.match(name))


def find_cycling_csvs(root: Path) -> list[Path]:
    root = Path(root)
    return sorted(p for p in root.rglob("*.csv") if is_cycling_file(p.name))


def latest_day_dir(root: Path) -> Path | None:
    """The most recent YYMMDD folder (by name) that contains cycling files."""
    days = {}
    for p in find_cycling_csvs(root):
        for parent in p.parents:
            if _DAY.match(parent.name):
                days[parent.name] = parent
                break
    if not days:
        return None
    return days[max(days)]
