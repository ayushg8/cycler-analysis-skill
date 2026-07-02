"""
run_all.py  --  Master runner for the cycling battery analysis project.

Workflow
--------
1. Drop ALL CSV files (260526 formation + 260601 cycling) into  data/
2. Edit config.py if a new Test series or DOE appears
3. Run:  python run_all.py

Outputs per test  →  output/<TestN>/plots/   and   output/<TestN>/csv/
Cross-test plots  →  output/plots/

What runs
---------
  run.py       Discharge Capacity and Temperature vs 1C Cycle (plot + CSV)
  run_rpt.py   RPT extraction with 1C cycle labels and comparison rows (CSV)
  run_vcap.py  Voltage vs Capacity panels every VCAP_STEP 1C cycles (plot)
  run_dqdv.py  dQ/dV charge and discharge evolution panels (cross-test plot)
"""

import re
import sys
import time
from pathlib import Path

import config as cfg
import run        as _run
import run_rpt    as _run_rpt
import run_vcap   as _run_vcap
import run_dqdv   as _run_dqdv

from paths import DATA_DIR


def detect_tests():
    """Scan data/ and return sorted list of test IDs present in config.TESTS."""
    found = set()
    for f in DATA_DIR.glob("*.csv"):
        m = re.search(r"_(Test\d+)_", f.name, re.IGNORECASE)
        if m:
            found.add(m.group(1))
    return sorted(t for t in found if t in cfg.TESTS)


def section(title):
    width = 54
    bar   = "=" * width
    print("\n" + bar)
    print("  " + title)
    print(bar)


def main():
    t0 = time.time()

    csv_files = list(DATA_DIR.glob("*.csv"))
    if not csv_files:
        print("ERROR: No CSV files found in data/  -- drop your files there first.")
        sys.exit(1)

    tests = detect_tests()
    if not tests:
        print("ERROR: No files matched any test series defined in config.TESTS.")
        print("  Files found: " + str([f.name for f in csv_files[:5]]))
        sys.exit(1)

    print("\nDetected test series : " + str(tests))
    print("Total CSV files      : " + str(len(csv_files)))

    # ── Per-test analyses ─────────────────────────────────────────────────────
    for tid in tests:
        temp_c = cfg.TESTS[tid].get("temp_c", "?")
        section(tid + "  (" + str(temp_c) + " °C)")

        print("\n[1/3] Capacity & Temperature plots + CSV")
        try:
            _run.main(tid)
        except Exception as e:
            print("  ERROR in run.py: " + str(e))

        print("\n[2/3] RPT extraction")
        try:
            _run_rpt.main(tid)
        except Exception as e:
            print("  ERROR in run_rpt.py: " + str(e))

        print("\n[3/3] Voltage vs Capacity panels")
        try:
            _run_vcap.main(tid)
        except Exception as e:
            print("  ERROR in run_vcap.py: " + str(e))

    # ── Cross-test dQ/dV ─────────────────────────────────────────────────────
    section("dQ/dV  (all tests combined)")
    try:
        _run_dqdv.main()
    except Exception as e:
        print("  ERROR in run_dqdv.py: " + str(e))

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = round(time.time() - t0, 1)
    section("Done  (" + str(elapsed) + " s)")
    print("\nOutputs:")
    for tid in tests:
        print("  output/" + tid + "/plots/   -- capacity, temperature, V-cap panels")
        print("  output/" + tid + "/csv/     -- cycling_all_DOEs.csv, rpt_all_DOEs.csv")
    print("  output/plots/          -- dQ/dV charge and discharge evolution")
    print()


if __name__ == "__main__":
    main()
