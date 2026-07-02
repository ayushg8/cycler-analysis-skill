# run_summary.py -- Cycling discharge capacity + max temperature summary CSV
#
# Output: output/<TestN>/csv/cycling_summary.csv
# Format: wide -- one row per 10-cycle interval (rounded to nearest 10),
#         columns grouped by DOE: Cycle | DOE1 Cap | DOE1 MaxT | DOE2 Cap | ...
# Two-row header: row1 = DOE names (repeated over 2 cols each), row2 = field names
#
# Usage:
#   python run_summary.py          # all tests
#   python run_summary.py Test4    # one test only

import sys
import re
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import config as cfg
from extract import load_csv, build_cycle_map

from paths import DATA_DIR, OUT_DIR as OUT_BASE
RPT_INTERVAL  = 126
_C10_RPT_SPAN = 26
CYCLE_STEP    = 10   # output every 10 cycles


def extract_run_id(filename):
    m = re.search(r"_Test\d+_([^_]+)_", filename, re.IGNORECASE)
    return m.group(1) if m else Path(filename).stem


def extract_test_id(filename):
    m = re.search(r"_(Test\d+)_", filename, re.IGNORECASE)
    return m.group(1) if m else None


def is_formation_file(df):
    cols = df.columns
    m = [c for c in cols if "_C2_Type" in c]
    return bool(m) and (df[m[0]] == "CC/D").sum() > 900


def count_rpt_blocks(df):
    cols = df.columns
    n = 0
    for rpt in range(0, 4000, RPT_INTERVAL):
        if any("_C" + str(2 + rpt) + "_Type" in c for c in cols):
            n += 1
        else:
            break
    return n


def get_current_min(test_id):
    rate = cfg.TESTS.get(test_id, {}).get("rate", "1C")
    return cfg.CURRENT_2C_MIN if rate == "2C" else cfg.CURRENT_1C_MIN


def get_rpt_exclude_cycles(df):
    exclude = set()
    cols    = df.columns
    for k in range(100):
        start = 2 + k * RPT_INTERVAL
        if not any("_C" + str(start) + "_Type" in c for c in cols):
            break
        for cyc in range(start, start + _C10_RPT_SPAN):
            exclude.add(cyc)
    return exclude


def extract_dis_data(df, cycle_map):
    """
    For each cycle in cycle_map, extract last CC/D capacity (Ah) and max T (C).
    Returns dict: {cycle_label: (capacity_ah, max_temp_c)}
    """
    result = {}
    cols   = df.columns
    for actual_cyc, label in cycle_map.items():
        col_str = "_C" + str(actual_cyc) + "_Type"
        matches = [c for c in cols if col_str in c]
        if not matches:
            continue
        col  = matches[0]
        ci   = cols.get_loc(col)
        mask = df[col] == "CC/D"
        if not mask.any():
            continue
        dis_df = df[mask]
        try:
            cap   = round(float(dis_df.iloc[-1, ci + 4]), 3)
            max_t = round(float(dis_df.iloc[:, ci + 6].astype(float).max()), 1)
            result[label] = (cap, max_t)
        except Exception:
            continue
    return result


def snap_to_10(cycle_label):
    """Round cycle label to nearest 10."""
    return round(cycle_label / 10) * 10


def load_doe_files(test_id):
    formation = {}
    cycling   = {}
    for fpath in sorted(DATA_DIR.glob("*.csv")):
        if extract_test_id(fpath.name) != test_id:
            continue
        doe = extract_run_id(fpath.name)
        try:
            df = load_csv(fpath)
        except Exception as e:
            print("  WARNING: " + fpath.name + " -- " + str(e))
            continue
        if is_formation_file(df):
            score = int((df[[c for c in df.columns if "_C2_Type" in c][0]] == "CC/D").sum())
            if doe not in formation or score > formation[doe][1]:
                formation[doe] = (df, score)
        else:
            score = count_rpt_blocks(df)
            if doe not in cycling or score > cycling[doe][1]:
                cycling[doe] = (df, score)
    return {
        doe: {
            "formation": formation.get(doe, (None,))[0],
            "cycling":   cycling.get(doe,   (None,))[0],
        }
        for doe in sorted(set(list(formation) + list(cycling)))
    }


def run_test(test_id):
    csv_dir = OUT_BASE / test_id / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    current_min = get_current_min(test_id)
    doe_files   = load_doe_files(test_id)
    if not doe_files:
        print("  No files for " + test_id)
        return

    print("  DOEs: " + str(sorted(doe_files.keys())))

    # DOE order
    doe_order = []
    seen = set()
    for grp in cfg.DOE_GROUPS:
        for doe in grp["does"]:
            if doe in doe_files and doe not in seen:
                doe_order.append(doe)
                seen.add(doe)
    for doe in sorted(doe_files):
        if doe not in seen:
            doe_order.append(doe)

    # Build data per DOE: {doe: {snapped_cycle: (cap, max_t)}}
    doe_data = {}
    for doe in doe_order:
        df_526 = doe_files[doe]["formation"]
        df_601 = doe_files[doe]["cycling"]
        if df_601 is None:
            continue

        if df_526 is not None:
            _, offset = build_cycle_map(df_526, current_1c_min=current_min)
        else:
            offset = 0

        exclude   = get_rpt_exclude_cycles(df_601)
        cycle_map, _ = build_cycle_map(df_601, count_offset=offset,
                                       current_1c_min=current_min,
                                       exclude_cycles=exclude)
        if not cycle_map:
            continue

        raw = extract_dis_data(df_601, cycle_map)
        if not raw:
            continue

        # Determine anchor: snap first label to nearest 10
        first_label = min(raw.keys())
        anchor      = snap_to_10(first_label)

        # For each raw label, map it to the nearest 10-cycle grid point
        # Keep only one value per grid point (closest raw cycle wins)
        grid = {}
        for label, vals in raw.items():
            snapped = round(label / CYCLE_STEP) * CYCLE_STEP
            # Only include snapped values >= anchor
            if snapped < anchor:
                continue
            if snapped not in grid:
                grid[snapped] = vals
            else:
                # keep the one whose raw label is closer to the snapped value
                existing_dist = abs(label - snapped)
                if existing_dist < abs(list(raw.keys())[0] - snapped):
                    grid[snapped] = vals

        doe_data[doe] = grid
        labels = sorted(grid.keys())
        print("    " + doe + ": " + str(len(labels)) + " grid pts, "
              + str(labels[0]) + "-" + str(labels[-1]))

    if not doe_data:
        print("  No data for " + test_id)
        return

    # Union of all snapped cycle labels, sorted
    all_cycles = sorted(set(c for d in doe_data.values() for c in d.keys()))

    # Build CSV lines
    rate_label = cfg.TESTS.get(test_id, {}).get("rate", "1C")
    active_does = [d for d in doe_order if d in doe_data]

    # Row 1: DOE headers (blank for Cycle col, then DOE name repeated twice)
    row1 = [rate_label + " Cycle"]
    for doe in active_does:
        row1.append(doe)
        row1.append("")

    # Row 2: field names
    row2 = [""]
    for _ in active_does:
        row2.append("Cap (Ah)")
        row2.append("Max T (degC)")

    lines = [",".join(row1), ",".join(row2)]

    for cyc in all_cycles:
        row = [str(cyc)]
        for doe in active_does:
            if cyc in doe_data[doe]:
                cap, max_t = doe_data[doe][cyc]
                row.append(str(cap))
                row.append(str(max_t))
            else:
                row.append("")
                row.append("")
        lines.append(",".join(row))

    out = csv_dir / "cycling_summary.csv"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("  Saved " + out.name)


def main(filter_test=None):
    tests = sorted(cfg.TESTS.keys()) if filter_test is None else [filter_test]
    for tid in tests:
        print("\n--- Summary: " + tid + " ---")
        run_test(tid)


if __name__ == "__main__":
    filter_test = sys.argv[1] if len(sys.argv) > 1 else None
    main(filter_test)
