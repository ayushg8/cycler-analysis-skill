# Cycler Analysis Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Package IBC's cycler analysis as a self-contained Claude Code skill Kunal invokes: it locates the latest cycling CSVs in his Drive-synced folder, runs the full analysis, and shows and saves the plots.

**Architecture:** Reuse the tested analysis engine from `cycler-automation` (Kunal's runners + `discover`/`configgen`), copied into a self-contained `engine/`. Add a `locate.py` that finds the plain `Test#_DOE#` cycling files inside the nested `cycler → month → day` Drive layout, and a `run_analysis.py` entrypoint that ties locate → discover → config → `run_all` → save. A `SKILL.md` tells Claude how to drive it, including the Sheet source and the locate fallback.

**Tech Stack:** Python 3.11+ (engine uses `from __future__ import annotations`, so 3.9 also runs), pandas, numpy, matplotlib, scipy, pytest. Delivered as a Claude Code skill folder.

## Global Constraints

- Reuse the analysis engine **unchanged except for the bundling import fixes in Task 1**. No analysis-logic changes.
- **Cycling-file selection rule:** a file is cycling data iff its name matches `Test\d+_DOE\d+` with the Test number directly adjacent to the DOE (plain `{date}_Si100_Test{N}_DOE{M}_{temp}.csv`). Files with a protocol token between Test and DOE (`_OCV_`, `_3C_HPPC_DisCharge_`, etc.) are characterization and are skipped.
- **Self-contained:** the skill folder carries everything; no imports from `cycler-automation` or a `pipeline` package.
- **No live Google or network calls in tests.** The analysis path is tested on local sample CSVs; skip if absent.
- **No AI tells or em dashes** in anything Kunal-facing (the SKILL.md prose and the summary text the entrypoint prints).
- Real cycler data is confidential: never commit CSVs. `data/`, `output/`, and `work/` are gitignored.

## File Structure

```
cycler-analysis-skill/
  SKILL.md                 # Task 4: the skill definition + how Claude runs it
  engine/                  # Task 1: bundled analysis engine (from cycler-automation)
    config_template.py  extract.py  extract_rpt.py  plots.py
    run.py  run_summary.py  run_rpt.py  run_vcap.py  run_dqdv.py  run_all.py
    discover.py  configgen.py  paths.py  defaults.py
    config.py              # generated at runtime (gitignored)
  locate.py                # Task 2: find cycling CSVs in the nested Drive layout
  run_analysis.py          # Task 3: entrypoint (locate -> discover -> config -> run_all -> save)
  settings.py              # Task 5: default data path + results path (Kunal-configurable)
  tests/
    __init__.py  conftest.py  test_locate.py  test_run_analysis.py
  requirements.txt  README.md  SPEC.md  PLAN.md
  data/  output/  work/    # gitignored; sample CSVs placed in data/ for tests
```

### Core interfaces (the spine)

```python
# engine/defaults.py
PALETTE: list[str]

# engine/discover.py  (reused; after Task 1 fixes)
def parse_filename(name: str) -> dict | None       # {date,chem,test,doe,temp_c} or None
def discover(data_dir: Path) -> dict               # {"Test4": {"temp_c","rate","does":[...]}, ...}
def build_config(discovered: dict, overrides: dict) -> dict

# engine/configgen.py  (reused; after Task 1 fixes)
def write_config(cfg: dict, out_path: Path) -> None

# locate.py
def is_cycling_file(name: str) -> bool             # plain Test#_DOE# only (skips protocol tokens)
def find_cycling_csvs(root: Path) -> list[Path]    # recurse the whole tree, matching files
def latest_day_dir(root: Path) -> Path | None      # deepest YYMMDD folder with cycling files, most recent

# run_analysis.py
def run(data_root: Path, out_dir: Path, work_dir: Path) -> dict   # {tests, does, plots:[...], csvs:[...], summary}
def main(argv: list[str] | None = None) -> int     # CLI: --data/--auto/--out/--work
```

---

### Task 1: Scaffold the skill and bundle the analysis engine

**Files:**
- Create: `cycler-analysis-skill/.gitignore`, `requirements.txt`, `engine/defaults.py`, `tests/__init__.py`, `tests/conftest.py`
- Copy: the engine scripts from `../cycler-automation` into `engine/`
- Modify (bundling fixes): `engine/discover.py`, `engine/configgen.py`

**Interfaces:** Produces an importable, self-contained `engine/` where `run_all` and `discover` work.

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
*.egg-info/
data/
output/
work/
engine/config.py
.DS_Store
```

- [ ] **Step 2: Create `requirements.txt`**

```
pandas
numpy
matplotlib
scipy
pytest
```

- [ ] **Step 3: Copy the engine scripts** (run from the skill folder)

```bash
mkdir -p engine tests
cp ../cycler-automation/analysis/{config_template.py,extract.py,extract_rpt.py,plots.py,run.py,run_summary.py,run_rpt.py,run_vcap.py,run_dqdv.py,run_all.py,paths.py} engine/
cp ../cycler-automation/pipeline/{discover.py,configgen.py} engine/
```

- [ ] **Step 4: Create `engine/defaults.py`** (replaces the `pipeline.settings` dependency)

```python
"""Defaults the engine needs that used to live in pipeline.settings."""
PALETTE = ["#1F6FAF", "#E07020", "#2A9A2A", "#9B30FF",
           "#20AACC", "#C02020", "#8B5E3C", "#444444"]
```

- [ ] **Step 5: Fix `engine/discover.py` imports.** It currently adds a sibling `analysis` dir to the path and imports `pipeline.settings`. Make it self-contained.

Replace the top-of-file path/import block:
```python
_ANALYSIS = Path(__file__).resolve().parent.parent / "analysis"
if str(_ANALYSIS) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS))

from extract import load_csv  # noqa: E402
import config_template as ct  # noqa: E402
```
with:
```python
_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from extract import load_csv  # noqa: E402
import config_template as ct  # noqa: E402
from defaults import PALETTE  # noqa: E402
```
Then replace the settings import and every `_settings.PALETTE` usage. Find:
```python
from pipeline import settings as _settings  # type: ignore
```
Delete that line. Change `palette = _settings.PALETTE` (in `build_config`) to `palette = PALETTE`. Leave everything else identical.

- [ ] **Step 6: Fix `engine/configgen.py` template path.** Find:
```python
_TEMPLATE = Path(__file__).resolve().parent.parent / "analysis" / "config_template.py"
```
Replace with:
```python
_TEMPLATE = Path(__file__).resolve().parent / "config_template.py"
```

- [ ] **Step 7: Create `tests/__init__.py`** (empty) and **`tests/conftest.py`**

```python
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture
def sample_data_dir():
    d = ROOT / "data"
    if not any(d.glob("*.csv")):
        pytest.skip("sample CSVs not present in data/")
    return d
```

- [ ] **Step 8: Stage sample data for the later integration test** (gitignored; not committed)

```bash
mkdir -p data
cp ../cycler-automation/data/*.csv data/ 2>/dev/null || echo "no sample data to copy (integration test will skip)"
```

- [ ] **Step 9: Smoke-test the bundled engine.** Create `tests/test_engine_smoke.py`:

```python
import importlib, sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"

def test_engine_imports():
    sys.path.insert(0, str(ENGINE))
    import extract, discover, configgen, paths  # noqa: F401
    from discover import parse_filename
    assert parse_filename("260601_Si100_Test4_DOE1_25.csv")["test"] == "Test4"
```

- [ ] **Step 10: Run** — `python3 -m pytest tests/test_engine_smoke.py -v`
Expected: PASS.

- [ ] **Step 11: git init + commit**

```bash
git init -q && git add -A
git ls-files | grep -iE '\.csv$' && echo "ERROR: CSV staged" || echo "no csv staged (good)"
git commit -q -m "chore: scaffold skill + bundle analysis engine

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `locate.py` — find cycling files in the nested Drive layout

**Files:** Create `locate.py`, `tests/test_locate.py`.

**Interfaces:**
- Consumes: `engine/discover.parse_filename` (via the cycling regex; re-implemented locally to avoid engine path setup in this module).
- Produces: `is_cycling_file(name) -> bool`, `find_cycling_csvs(root) -> list[Path]`, `latest_day_dir(root) -> Path | None`.

- [ ] **Step 1: Write the failing test** — `tests/test_locate.py`

```python
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
```

- [ ] **Step 2: Run, expect fail** — `python3 -m pytest tests/test_locate.py -v` → `ModuleNotFoundError: locate`

- [ ] **Step 3: Create `locate.py`**

```python
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
```

- [ ] **Step 4: Run, expect pass** — `python3 -m pytest tests/test_locate.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -m "feat: locate cycling CSVs in the nested Drive layout

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `run_analysis.py` — the entrypoint

**Files:** Create `run_analysis.py`, `tests/test_run_analysis.py`.

**Interfaces:**
- Consumes: `locate.find_cycling_csvs`, `engine.discover.discover`, `engine.discover.build_config`, `engine.configgen.write_config`, `engine.run_all` (via `run_summary` for the fast test path).
- Produces: `run(data_root, out_dir, work_dir) -> dict`, `main(argv) -> int`.

- [ ] **Step 1: Write the failing test** — `tests/test_run_analysis.py`

```python
from pathlib import Path
from run_analysis import run

def test_run_on_sample_data(sample_data_dir, tmp_path):
    result = run(sample_data_dir, tmp_path / "out", tmp_path / "work")
    assert "Test4" in result["tests"] or "Test5" in result["tests"]
    # produced at least one CSV summary and the config was generated
    assert result["csvs"], "expected summary CSVs"
    assert (Path(__file__).resolve().parent.parent / "engine" / "config.py").exists()
```

- [ ] **Step 2: Run, expect fail** — `python3 -m pytest tests/test_run_analysis.py -v` → `ModuleNotFoundError: run_analysis`

- [ ] **Step 3: Create `run_analysis.py`**

```python
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
```

- [ ] **Step 4: Run, expect pass** — `python3 -m pytest tests/test_run_analysis.py -v`
Expected: PASS if sample data is present in `data/` (else SKIP). If the full `run_all` is slow, this test still completes in a few seconds on the small sample.

- [ ] **Step 5: Run the whole suite** — `python3 -m pytest -q`. Expected: all green (render-free; no network).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -q -m "feat: run_analysis entrypoint (locate -> discover -> config -> run_all -> save)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `SKILL.md` — the skill definition

**Files:** Create `SKILL.md`.

- [ ] **Step 1: Create `SKILL.md`**

````markdown
---
name: cycler-analysis
description: Use when Kunal wants his weekly IBC cycler analysis. Finds the latest cycling data in his Drive, runs the full analysis (capacity, state of health, temperature, voltage-vs-capacity, dQ/dV, RPT), and shows and saves the plots. Runs on his own account, so his Drive access is all it needs.
---

# Cycler Analysis

Reproduce Kunal's weekly scripts-and-graphs routine in one invocation, running as him in Claude Code.

## Preflight
Confirm you can run Python and that the analysis dependencies are installed (`pip install -r requirements.txt` inside the skill folder). The heavy files need real Python, which the terminal provides.

## Data source
Two possibilities. Detect which one you were handed.

1. **A folder of cycler CSVs (default).** Read the local Google Drive for Desktop copy of the "Cycler data" drive at the path in `settings.py` (or a folder Kunal names). The layout is `1Cycler`/`2Cycler` → month (`MM.YY`) → day (`YYMMDD`) → files. Only the **cycling** files matter: `{date}_Si100_Test{N}_DOE{M}_{temp}.csv`, where Test sits directly next to DOE. Files with a protocol token between them (`_OCV_`, `_3C_HPPC_DisCharge_`, ...) are characterization; skip them. `locate.py` and `run_analysis.py` already apply this rule.
2. **A Google Sheet** (for example `Si100% rawdata.xlsx`). Read the sheet, understand its columns (cycles, capacities, DOEs), and plot the cycle/health data directly. Adapt to whatever layout it has; do not assume a fixed one.

## Run it (CSV folder)
From the skill folder:
`python run_analysis.py --data "<the Cycler data folder>" --out "<results folder>"`
It flattens the cycling CSVs, auto-discovers the tests/DOEs, generates the config, runs the full analysis, and writes the plots and CSVs to the results folder. Then show Kunal the plots (Read each PNG) and a one-line summary.

## If the data cannot be found
If `run_analysis.py` reports zero files ingested, the layout may have shifted. Locate the data before giving up: list the "Cycler data" folder, walk `1Cycler`/`2Cycler` → month → day, and confirm where the plain `Test#_DOE#` files are, then re-run with the corrected `--data`. As a visual last resort, drive the browser to navigate the Drive (the way the drive was mapped during design). The browser is only for finding files; the analysis reads their contents from the synced local folder.

## Steering
Kunal can narrow or shape the run in plain language: "just Test 4", "group DOE1 to 5 and keep 7 and 8 separate", "focus on capacity fade", "use last week's folder". New tests or DOEs appear automatically, since selection is by the filename pattern, so he never configures anything.

## Writing rules
Anything you write for Kunal (summaries, captions) is plain and human. No em dashes. None of: comprehensive, robust, leverage, delve, navigate, intricate, underscore, crucial, essential.
````

- [ ] **Step 2: Manual verification.** Confirm the front matter parses (name + description), every command references a real file in this skill, and the writing rules match CLAUDE.md's AI-tells list.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -q -m "feat: cycler-analysis SKILL.md"
```

---

### Task 5: settings, README, and finalize

**Files:** Create `settings.py`, `README.md`.

- [ ] **Step 1: Create `settings.py`**

```python
"""Kunal-configurable defaults. Set DATA_ROOT to the local Google Drive for
Desktop path of the 'Cycler data' drive, and RESULTS_DIR to where plots should
be saved. These are read by the skill, not committed with real paths."""
from pathlib import Path

# Example (macOS Drive for Desktop): "~/Library/CloudStorage/GoogleDrive-<kunal>/Shared drives/Cycler data"
DATA_ROOT = ""     # fill in during setup
RESULTS_DIR = str(Path.home() / "cycler-results")
```

- [ ] **Step 2: Create `README.md`**

```markdown
# Cycler Analysis Skill

A Claude Code skill that runs IBC's cycler analysis on demand. Invoke it in Claude Code and it finds the latest cycling data in the Drive-synced "Cycler data" folder, runs the full analysis (capacity, state of health, temperature, voltage-vs-capacity, dQ/dV, RPT), and shows and saves the plots. It runs as you, so your Drive access is all it needs. No service account, no automation, no email.

## One-time setup
1. Install Claude Code.
2. Install Google Drive for Desktop and confirm the "Cycler data" drive syncs locally.
3. Copy this folder to `~/.claude/skills/cycler-analysis/`.
4. `pip install -r requirements.txt`.
5. Set `DATA_ROOT` in `settings.py` to the local synced "Cycler data" path.

## Use
In Claude Code: "run the cycler analysis." Steer in plain English ("just Test 4", "group DOE1 to 5"). See `SPEC.md` for the design.

## Tests
`python3 -m pytest -q`
```

- [ ] **Step 3: Run the full suite** — `python3 -m pytest -q`. Expected: green (integration test skips if no sample data).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -q -m "docs: settings + README"
```

---

## Self-Review

**Spec coverage:** engine reuse (Task 1), cycling-file selection rule (Task 2 `is_cycling_file`, verified pattern), nested cycler/month/day locating (Task 2), run end-to-end (Task 3), show/save + summary (Task 3 + SKILL.md), Sheet source (SKILL.md, Claude-adaptive), locate fallback incl. browser (SKILL.md), auto-discovery + plain-English steering (SKILL.md + reused discover), install/setup (Task 5 README + settings), retired pipeline not carried over (only engine copied). All covered.

**Placeholder scan:** no TBD/TODO; every code/test step has real content. `settings.DATA_ROOT` is intentionally blank (filled at setup), not a plan placeholder.

**Type consistency:** `is_cycling_file`/`find_cycling_csvs`/`latest_day_dir` consistent across Task 2 and Task 3; `discover`/`build_config`/`write_config` names match the reused engine; `run`/`main` signatures consistent Task 3 → SKILL.md commands.

**Known soft spots (acceptable):** the Sheet path is Claude-adaptive (no unit test, verified on first real run); `run_analysis` flattens all matching cycling CSVs and relies on `run_all`'s best-file-per-DOE logic to pick the latest snapshot, which is correct but processes redundant older snapshots (the SKILL.md notes Kunal can point `--data` at a recent month to bound it); heavy compute is fine in the terminal (the supported environment).
