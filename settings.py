"""Kunal-configurable defaults. Set DATA_ROOT to the local Google Drive for
Desktop path of the 'Cycler data' drive, and RESULTS_DIR to where plots should
be saved. These are read by the skill, not committed with real paths."""
from pathlib import Path

# Example (macOS Drive for Desktop): "~/Library/CloudStorage/GoogleDrive-<kunal>/Shared drives/Cycler data"
DATA_ROOT = ""     # fill in during setup
RESULTS_DIR = str(Path.home() / "cycler-results")
