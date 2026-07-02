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
