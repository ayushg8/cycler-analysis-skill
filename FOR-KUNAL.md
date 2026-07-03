# Cycler Analysis

This runs your weekly cycler analysis in one step. You open Claude, tell it to run the cycler analysis, and it finds the latest data in your Drive, runs the full analysis, and shows you the plots: discharge capacity, state of health (retention %), temperature, voltage vs capacity, dQ/dV, and the RPT table with internal resistance. It only reads the data; it never changes it.

It runs on your own machine, as you, so it reaches the Cycler data Shared Drive directly. Nothing to share, nothing to schedule.

## One-time setup (Ayush will do this with you, about 15 minutes)

1. Install Claude Code.
2. Install Google Drive for Desktop and sign in, so the "Cycler data" Shared Drive shows up as a normal folder on your computer.
3. Put the `cycler-analysis` folder into your Claude skills folder (`~/.claude/skills/cycler-analysis/`).
4. In a terminal, inside that folder, run `pip install -r requirements.txt`.
5. Set `DATA_ROOT` in `settings.py` to the local "Cycler data" path from step 2.

## How to use it (every time)

Open Claude Code and say:

> run the cycler analysis

That is it. It pulls the newest cycling data, runs everything, and shows you the plots.

You can steer it in plain English whenever you want:

- "just Test 4"
- "group DOE1 to 5 and keep 7 and 8 separate"
- "focus on capacity fade"
- "use last week's folder"

New tests or DOEs show up on their own. You never configure anything.

## Good to know

- It uses the plain cycling files (`..._Test4_DOE1_25.csv`) and skips the characterization runs (OCV, HPPC) on its own.
- Results are saved to a folder and shown in the session, so you can keep them or pass them along.
- If it ever cannot find the data, it looks through the Drive to relocate it before giving up.
