# run.py  —  Discharge Capacity and Temperature plots + CSV per test
#
# X-axis: total 1C cycle count (carried across 260526 and 260601 files)
# CSV columns: 1C Cycle | DOE1 Cap (Ah) | DOE1 Max T (°C) | DOE2 Cap (Ah) | ...
#
# Usage:
#   python run.py          # all tests in config.TESTS
#   python run.py Test4    # one test only

import sys
import re
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as cfg
from extract import load_csv, extract_cycling_data, build_cycle_map

from paths import DATA_DIR, OUT_DIR as OUT_BASE
RPT_INTERVAL = 126


# ── File helpers ──────────────────────────────────────────────────────────────

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
        if any(f"_C{2 + rpt}_Type" in c for c in cols):
            n += 1
        else:
            break
    return n


# ── Load and remap cycling data ───────────────────────────────────────────────

def load_runs_for_test(test_id):
    """
    Returns {doe: df} where df has columns [cycle_1c, capacity_ah, temperature].
    cycle_1c = total 1C count across both files.
    Best file per DOE = most cycling data points.
    """
    # Collect best formation + cycling file per DOE
    formation: dict = {}   # doe → (df, score)
    cycling:   dict = {}   # doe → (df, score)

    for fpath in sorted(DATA_DIR.glob("*.csv")):
        if extract_test_id(fpath.name) != test_id:
            continue
        doe = extract_run_id(fpath.name)
        try:
            df = load_csv(fpath)
        except Exception as e:
            print("  WARNING: " + fpath.name + " — " + str(e))
            continue

        if is_formation_file(df):
            score = int((df[[c for c in df.columns if "_C2_Type" in c][0]] == "CC/D").sum())
            if doe not in formation or score > formation[doe][1]:
                formation[doe] = (df, score)
        else:
            # Count 1C cycles as proxy score
            cycle_map, score = build_cycle_map(df, current_1c_min=cfg.CURRENT_1C_MIN)
            if doe not in cycling or score > cycling[doe][1]:
                cycling[doe] = (df, score)

    results = {}
    for doe in sorted(set(list(formation.keys()) + list(cycling.keys()))):
        df_526 = formation.get(doe, (None,))[0]
        df_601 = cycling.get(doe, (None,))[0]
        if df_601 is None:
            continue   # no main cycling data → skip

        # Offset from 260526
        if df_526 is not None:
            _, offset = build_cycle_map(df_526, current_1c_min=cfg.CURRENT_1C_MIN)
        else:
            offset = 0

        # Build 1C map for 260601
        cycle_map_601, _ = build_cycle_map(df_601, count_offset=offset,
                                           current_1c_min=cfg.CURRENT_1C_MIN)

        # Extract cycling data (existing logic, returns raw cycle numbers)
        df_cyc = extract_cycling_data(
            df_601,
            start_cycle=cfg.CYCLING_START_CYCLE,
            end_cycle=cfg.CYCLING_END_CYCLE,
            increment=cfg.CYCLING_INCREMENT,
            rpt_counter_reset=cfg.RPT_COUNTER_RESET,
            rpt_skip=cfg.RPT_SKIP,
        )
        if df_cyc.empty:
            continue

        # Remap raw cycle → 1C count
        df_cyc["cycle_1c"] = df_cyc["cycle"].map(cycle_map_601)
        df_cyc = df_cyc.dropna(subset=["cycle_1c"])
        df_cyc["cycle_1c"] = df_cyc["cycle_1c"].astype(int)

        print("    " + doe + ": " + str(len(df_cyc)) + " pts, "
              "1C count " + str(df_cyc["cycle_1c"].iloc[0])
              + "–" + str(df_cyc["cycle_1c"].iloc[-1]))
        results[doe] = df_cyc

    return results


# ── Plotting ──────────────────────────────────────────────────────────────────

def run_style(run_id):
    entry = cfg.RUNS.get(run_id, {})
    return {
        "label":  entry.get("label",  run_id),
        "color":  entry.get("color",  cfg.DEFAULT_COLOR),
        "marker": entry.get("marker", cfg.DEFAULT_MARKER),
    }


def make_plot(all_runs, y_col, ylabel, title, out_path):
    fig, ax = plt.subplots(figsize=cfg.FIGURE_SIZE)
    ax.set_facecolor("white"); fig.patch.set_facecolor("white")
    ax.grid(True, color="#e0e0e0", linewidth=0.8)
    ax.set_axisbelow(True)
    for doe, df in all_runs.items():
        s = run_style(doe)
        ax.plot(df["cycle_1c"], df[y_col],
                linestyle=cfg.LINE_STYLE, marker=s["marker"],
                markersize=cfg.MARKER_SIZE, color=s["color"], label=s["label"])
    ax.set_xlabel("1C Cycle Count", fontsize=cfg.FONT_SIZE_AXIS, fontfamily=cfg.FONT_FAMILY)
    ax.set_ylabel(ylabel,           fontsize=cfg.FONT_SIZE_AXIS, fontfamily=cfg.FONT_FAMILY)
    ax.set_title(title,             fontsize=cfg.FONT_SIZE_TITLE, fontfamily=cfg.FONT_FAMILY)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.13),
        ncol=8,
        frameon=False,
        fontsize=cfg.FONT_SIZE_LEGEND,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=cfg.PLOT_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  ✓  " + out_path.name)


# ── CSV output ────────────────────────────────────────────────────────────────────────────────

def save_csv(all_runs, out_path):
    """
    Wide-format CSV with two-row merged header:
      Row 1: 1C Cycle | DOE1 |    | DOE2 |    | ...
      Row 2:           | Cap (Ah) | Max T (degC) | ...
    """
    does       = sorted(all_runs.keys())
    all_cycles = sorted({cyc for df in all_runs.values() for cyc in df["cycle_1c"]})

    h1 = ["1C Cycle"]
    for doe in does:
        h1 += [doe, ""]
    h2 = [""] + ["Cap (Ah)", "Max T (degC)"] * len(does)

    lines = [",".join(h1), ",".join(h2)]
    for cyc in all_cycles:
        row = [str(cyc)]
        for doe in does:
            df    = all_runs[doe]
            match = df[df["cycle_1c"] == cyc]
            if not match.empty:
                row.append(str(round(float(match["capacity_ah"].iloc[0]), 3)))
                row.append(str(round(float(match["temperature"].iloc[0]),  1)))
            else:
                row += ["", ""]
        lines.append(",".join(row))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("  ✓  " + out_path.name)


# ── Main ────────────────────────────────────────────────────────────────────────────────

def main(test_id=None):
    tests = [test_id] if test_id else sorted(cfg.TESTS.keys())
    for tid in tests:
        info     = cfg.TESTS.get(tid, {})
        temp_c   = info.get("temp_c", "?")
        rate     = info.get("rate", "1C")
        plot_dir = OUT_BASE / tid / "plots"
        csv_dir  = OUT_BASE / tid / "csv"
        plot_dir.mkdir(parents=True, exist_ok=True)
        csv_dir.mkdir(parents=True, exist_ok=True)

        print("  Loading runs for " + tid + " ...")
        all_runs = load_runs_for_test(tid)
        if not all_runs:
            print("  No data found for " + tid)
            continue

        title_base = tid + "  (" + str(temp_c) + " °C  |  " + rate + ")"

        make_plot(
            all_runs, "capacity_ah", "Discharge Capacity (Ah)",
            "Discharge Capacity vs 1C Cycle  --  " + title_base,
            plot_dir / (tid + "_capacity.png"),
        )
        make_plot(
            all_runs, "temperature", "Max Temperature (°C)",
            "Max Temperature vs 1C Cycle  --  " + title_base,
            plot_dir / (tid + "_temperature.png"),
        )
        save_csv(all_runs, csv_dir / "cycling_summary.csv")


if __name__ == "__main__":
    test_id = sys.argv[1] if len(sys.argv) > 1 else None
    main(test_id)
