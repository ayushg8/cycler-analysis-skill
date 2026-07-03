---
name: cycler-analysis
description: Use when Kunal wants his weekly IBC cycler analysis. Finds the latest cycling data in his Drive, runs the full analysis (capacity, state of health, temperature, voltage-vs-capacity, dQ/dV, RPT), and shows and saves the plots. Runs on his own account, so his Drive access is all it needs.
---

# Cycler Analysis

Reproduce Kunal's weekly scripts-and-graphs routine in one invocation, running as him in Claude Code.

## First, run the setup check
Every invocation, start by running `python preflight.py` from the skill folder. If it prints `READY`, go straight to the run. If it prints `SETUP NEEDED`, walk Kunal through only the missing pieces, then re-run `preflight.py` until it says `READY`:

- **`missing_deps`** -- run `pip install -r requirements.txt` in the skill folder.
- **`data_root_unset`** or **`data_root_missing`** -- the skill needs the "Cycler data" Shared Drive available as a local folder. If preflight listed candidate folders, confirm the right one with Kunal and set `DATA_ROOT` in `settings.py` to it. If it listed none, ask Kunal to install Google Drive for Desktop (`https://www.google.com/drive/download/`), sign in with his IBC account, and wait for the "Cycler data" drive to finish syncing, then re-run `preflight.py` and it will find the folder.
- **`no_cycling_files`** -- the folder is set but empty, usually because the drive is still syncing or the wrong folder was picked. Ask Kunal to confirm syncing finished, or point `DATA_ROOT` at the right folder.

This only comes up on first use. Once `DATA_ROOT` is set and valid, the check passes silently and the skill runs straight through. The analysis itself needs real Python (pandas, scipy, matplotlib), which the terminal provides.

## Data source
Two possibilities. Detect which one you were handed.

1. **A folder of cycler CSVs (default).** Read the local Google Drive for Desktop copy of the "Cycler data" drive at the path in `settings.py` (or a folder Kunal names). The layout is `1Cycler`/`2Cycler` → month (`MM.YY`) → day (`YYMMDD`) → files. Only the **cycling** files matter: `{date}_Si100_Test{N}_DOE{M}_{temp}.csv`, where Test sits directly next to DOE. Files with a protocol token between them (`_OCV_`, `_3C_HPPC_DisCharge_`, ...) are characterization; skip them. `locate.py` and `run_analysis.py` already apply this rule.
2. **A Google Sheet** (for example `Si100% rawdata.xlsx`). Read the sheet, understand its columns (cycles, capacities, DOEs), and plot the cycle/health data directly. Adapt to whatever layout it has; do not assume a fixed one.

## Run it (CSV folder)
From the skill folder:
`python run_analysis.py --data "<the Cycler data folder>" --out "<results folder>"`
It flattens the cycling CSVs, auto-discovers the tests/DOEs, generates the config, runs the full analysis, and writes the plots and CSVs to the results folder. Then show Kunal the plots (Read each PNG) and a one-line summary.

## If the data cannot be found
If `run_analysis.py` reports zero files ingested, the layout may have shifted. Locate the data before giving up: list the "Cycler data" folder, walk `1Cycler`/`2Cycler` → month → day, and confirm where the plain `Test#_DOE#` files are, then re-run with the corrected `--data`. As a visual last resort, drive the browser to open the Drive folder (the way the drive was mapped during design). The browser is only for finding files; the analysis reads their contents from the synced local folder.

## Steering
Kunal can narrow or shape the run in plain language: "just Test 4", "group DOE1 to 5 and keep 7 and 8 separate", "focus on capacity fade", "use last week's folder". New tests or DOEs appear automatically, since selection is by the filename pattern, so he never configures anything.

## Writing rules
Anything you write for Kunal (summaries, captions) is plain and human. No em dashes. None of: comprehensive, robust, leverage, delve, navigate, intricate, underscore, crucial, essential.
