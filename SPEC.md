# Cycler Analysis Skill

**Design spec** · 2026-07-02 · Ayush G (IBC engagement)
**Status:** approved design, pre-implementation

---

## Context

Kunal runs a manual routine every week: pull the new cycler data, run his Python scripts, and look at the resulting graphs (capacity fade, state of health, temperature, voltage-vs-capacity, dQ/dV, RPT). This skill replaces that whole routine with a single invocation on his own Claude.

It also replaces the automated pipeline we built earlier (GitHub Action, service account, domain-wide delegation, the Apps Script bridge, control Sheet, cron, email). All of that is retired. The reason is simple: the cycler data lives in a Google Shared Drive locked to `@ibcbatt.com` members, and every attempt to give an external service account access hit that wall. Running the analysis **as Kunal, on his own Claude**, sidesteps the wall entirely, because his identity already has access. The analysis engine (his scripts plus the discovery and config code we built and tested) is reused unchanged.

## Goal

One invocation in Kunal's Claude Code reproduces his entire manual scripts-and-graphs routine: it finds the latest cycling data in his Drive, runs the full analysis, shows him the plots with a short summary, and saves them to a results folder. Adding a new test or DOE requires nothing from him.

## Non-goals

- No automated/scheduled runs, no email. This is on-demand, Kunal-invoked.
- No service account, no Drive API credentials, no domain delegation, no bridge. Access is via Kunal's own identity.
- Not a general "any dataset" pipeline. It targets IBC's cycler data specifically.

## Principles

- Runs as Kunal, so his access is the only access needed.
- Reuse the tested analysis engine; the new work is the skill wrapper and the data-locating.
- Make it dead simple for Kunal: one invocation, sensible defaults, plain-English steering.
- Robust to the messy, shifting Drive: locate the data each run rather than hardcoding a path.
- No AI tells or em dashes in anything Kunal-facing.

## Environment

- **Claude Code in the terminal** on Kunal's machine. The terminal runs the real Python (pandas, numpy, matplotlib, scipy) with no sandbox limits, which the heavy cycler files need. This is exactly how the engine was built and tested.
- **Google Drive for Desktop** syncs the "Cycler data" Shared Drive to a local folder on Kunal's machine. Because Drive for Desktop is logged in as Kunal, the locked Shared Drive simply appears as local files, with no external access, no API, no admin.

## The real Drive structure (verified in-browser, 2026-07-02)

The Shared Drive is "Cycler data" (`0AK5e1cZOK7xiUk9PVA`). It is messier than the tidy zip Kunal handed over:

```
Cycler data (shared drive)
├── 1Cycler/    (1Z1euoCRkoGBxzXwuXlQ8xbkVxYyQz4ff)
│   └── <MM.YY month>/          e.g. 06.26
│       └── <YYMMDD day>/       e.g. 260629  (the capture/snapshot date)
│           └── *.csv           the data files
├── 2Cycler/    (1-0vzkMrvoy-_0sWNP27dS81YrELJ8PlE)   same nesting
├── Run 8, Run 7, Run 6, NEWARE, LFP, DOE_EIS, Aging test, ...   (other folders, ignore)
└── Si100% rawdata.xlsx         (the spreadsheet source, see below)
```

Notes that matter:
- The data is nested **cycler → month (MM.YY) → day (YYMMDD) → files**.
- The **folder date is the capture date; the filename date is the test date**, and they differ.
- Filenames carry a protocol descriptor for characterization runs but not for cycling runs (see selection rule).
- Many unrelated folders sit at the root; the skill must not wander into them.

## File selection rule (verified)

The distinguisher between the cycling data (what the analysis needs) and everything else:

- **Cycling files (use these):** `{date}_Si100_Test{N}_DOE{M}_{temp}.csv` — `Test{N}` sits **directly next to** `_DOE{M}`, no token in between. Examples: `260601_Si100_Test4_DOE1_25.csv`, `260526_Si100_Test3_DOE4_45.csv`.
- **Characterization files (skip these):** a protocol token is wedged between Test and DOE. Examples: `260526_Si100_Test1_OCV_DOE8_25.csv`, `260626_Si100_Test1_3C_HPPC_DisCharge_DOE1_25.csv`.

The rule is exactly the regex the discovery code already uses (`Test\d+_DOE\d+`): it matches the plain cycling names and naturally skips the protocol-token files, because the token breaks the adjacency. Verified against the live drive, not just the zip.

## How it works

1. **Invoke.** Kunal runs the skill in Claude Code (for example, "run the cycler analysis").
2. **Locate the data.** By default the skill reads the local Drive-for-Desktop copy of the "Cycler data" drive, walks `1Cycler`/`2Cycler` → month → day, and collects the plain `Test#_DOE#` cycling CSVs (skipping OCV/HPPC and the unrelated root folders). If the local pull comes up empty or the layout has shifted, Claude falls back to navigating the Drive to relocate it: first the Drive connector, and as a visual last resort, driving the browser the way we did during design. The browser is for *finding* files; the analysis still reads their contents from the synced local copy.
3. **Understand and configure.** Auto-discover the tests, DOEs, temperature, and C-rate (reused discovery), generating the config the runners consume. No manual config.
4. **Run the analysis.** Execute the reused `run_all` engine: discharge capacity, state of health, max temperature, voltage-vs-capacity, dQ/dV, and the RPT table with internal resistance.
5. **Show and save.** Display the plots and a short summary in the session, and save the plots and CSVs to a results folder (which syncs back to Drive).

**Steering (plain English).** Kunal can say "just Test 4," "group DOE1 to 5 and keep 7 and 8 separate," "focus on capacity fade," or "use last week's folder." New tests or DOEs appear automatically, since discovery is by filename pattern.

## Alternate data source: a spreadsheet

Instead of the raw CSV folder, Kunal can point the skill at a Google Sheet in his Drive (for example `Si100% rawdata.xlsx`). The skill reads the sheet, and because Claude inspects it at runtime, it adapts to whatever columns are there (cycles, capacities, DOEs) and plots directly from it, rather than requiring a fixed layout. The skill auto-detects which source it was handed (a folder of CSVs versus a spreadsheet) and behaves accordingly.

## Packaging and install

A self-contained Claude Code skill folder so it is portable to Kunal's machine:

```
cycler-analysis-skill/
  SKILL.md                 # the skill: how Claude locates data, runs the engine, shows results
  engine/                  # the reused analysis engine (Kunal's runners + discovery + config gen)
    config_template.py  extract.py  extract_rpt.py  plots.py
    run.py  run_summary.py  run_rpt.py  run_vcap.py  run_dqdv.py  run_all.py
    discover.py  configgen.py  paths.py
  README.md  SPEC.md  PLAN.md
```

Install: drop the skill into Kunal's `~/.claude/skills/cycler-analysis/` (Ayush helps during the one-time setup). One-time setup also covers installing Claude Code and Google Drive for Desktop and pointing the skill's default data path at the synced "Cycler data" location.

## What is retired

The `cycler-automation` GitHub Action, `pipeline/ingest.py`, `pipeline/deliver.py`, `pipeline/main.py`, `.github/workflows/weekly.yml`, the three GitHub secrets, the domain-wide-delegation setup, the Apps Script bridge idea, and the control Sheet. The analysis engine from that repo lives on inside this skill.

## Setup steps (one-time, Ayush helps Kunal)

1. Install Claude Code in Kunal's terminal.
2. Install Google Drive for Desktop and confirm the "Cycler data" drive syncs locally.
3. Install the skill into `~/.claude/skills/cycler-analysis/`.
4. Configure the skill's default data path (the local synced "Cycler data" folder) and results folder.
5. First run together to confirm it finds the cycling files and produces the plots.

## Open questions and risks

1. **Heavy compute:** the terminal handles the full analysis (proven). If Kunal ever runs it in the Claude app instead, the sandbox may choke on the big files; the terminal is the supported path.
2. **Spreadsheet layout:** the `Si100% rawdata.xlsx` structure is unconfirmed; the skill adapts at runtime, but the first real run should verify the plots make sense.
3. **Which cyclers/dates by default:** default is the latest day folder across `1Cycler` and `2Cycler`; Kunal can override in plain English. Confirm this default matches his habit.
4. **Results destination:** a local results folder that syncs to Drive; confirm the exact location with Kunal at setup.
