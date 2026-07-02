# run_vcap.py  --  Voltage vs Capacity plots (every VCAP_STEP 1C cycles per DOE)
#
# Cycle labels use total 1C count across 260526 + 260601 files.
# Selects the first 1C cycle in 260601, then every VCAP_STEP cycles after that.
#
# Usage:
#   python run_vcap.py          # all tests
#   python run_vcap.py Test4    # one test only

import sys
import re
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as cfg
from extract import load_csv, build_cycle_map

from paths import DATA_DIR, OUT_DIR as OUT_BASE
RPT_INTERVAL = 126
_C10_RPT_SPAN = 26   # cycles per C/10 RPT block


# -- Rate helpers --------------------------------------------------------------

def get_current_min(test_id):
    rate = cfg.TESTS.get(test_id, {}).get("rate", "1C")
    return cfg.CURRENT_2C_MIN if rate == "2C" else cfg.CURRENT_1C_MIN


def get_rpt_exclude_cycles(df):
    exclude = set()
    cols = df.columns
    for k in range(100):
        start = 2 + k * RPT_INTERVAL
        if not any("_C" + str(start) + "_Type" in c for c in cols):
            break
        for cyc in range(start, start + _C10_RPT_SPAN):
            exclude.add(cyc)
    return exclude


# -- File helpers --------------------------------------------------------------

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


# -- Cycle selection via 1C map ------------------------------------------------

def select_vcap_cycles(cycle_map_601, step):
    """
    From the 1C cycle map of a 260601 file (already offset-adjusted),
    pick cycles to plot: first cycle available, then every `step` 1C cycles.

    Returns list of (actual_cycle, 1c_count) tuples, sorted by 1c_count.
    """
    if not cycle_map_601:
        return []

    sorted_pairs = sorted(cycle_map_601.items(), key=lambda x: x[1])
    first_count  = sorted_pairs[0][1]

    selected = []
    for actual_cyc, count in sorted_pairs:
        relative = count - first_count   # 0, 1, 2, ... steps into this file
        if relative == 0 or relative % step == 0:
            selected.append((actual_cyc, count))

    return selected


# -- Curve extraction ----------------------------------------------------------

def extract_curves(df, cyc):
    """Return (v_dis, q_dis, v_chg, q_chg) for a given actual cycle number."""
    cols = df.columns
    m = [c for c in cols if "_C" + str(cyc) + "_Type" in c]
    if not m:
        return None, None, None, None
    ci  = cols.get_loc(m[0])
    tc  = df[m[0]]
    dis = tc == "CC/D"
    chg = tc.isin(["CC/C", "CC/CV/C"])
    v_d = df.loc[dis].iloc[:, ci + 2].astype(float).values if dis.sum() else None
    q_d = df.loc[dis].iloc[:, ci + 4].astype(float).values if dis.sum() else None
    v_c = df.loc[chg].iloc[:, ci + 2].astype(float).values if chg.sum() else None
    q_c = df.loc[chg].iloc[:, ci + 4].astype(float).values if chg.sum() else None
    return v_d, q_d, v_c, q_c


# -- Per-test runner -----------------------------------------------------------

def run_test(test_id, files):
    plot_dir = OUT_BASE / test_id / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    test_cfg = cfg.TESTS.get(test_id, {})
    temp_c   = test_cfg.get("temp_c", "?")
    step     = cfg.VCAP_STEP

    # Collect best formation + cycling file per DOE
    formation = {}
    cycling   = {}

    for fpath in sorted(files):
        doe = extract_run_id(fpath.name)
        try:
            df = load_csv(fpath)
        except Exception:
            continue

        if is_formation_file(df):
            n_dis = int((df[[c for c in df.columns if "_C2_Type" in c][0]] == "CC/D").sum())
            if doe not in formation or n_dis > formation[doe][1]:
                formation[doe] = (df, n_dis)
        else:
            score = count_rpt_blocks(df)
            if doe not in cycling or score > cycling[doe][1]:
                cycling[doe] = (df, score)

    # Build per-DOE data: {doe: (df_601, selected_cycles)}
    doe_data = {}
    for doe in sorted(set(list(formation.keys()) + list(cycling.keys()))):
        df_526 = formation.get(doe, (None,))[0]
        df_601 = cycling.get(doe, (None,))[0]
        if df_601 is None:
            continue

        cur_min = get_current_min(test_id)

        # Offset from formation file
        if df_526 is not None:
            _, offset = build_cycle_map(df_526, current_1c_min=cur_min)
        else:
            offset = 0

        # 1C map for 260601, excluding RPT blocks
        exclude_601 = get_rpt_exclude_cycles(df_601)
        cycle_map_601, _ = build_cycle_map(df_601, count_offset=offset,
                                           current_1c_min=cur_min,
                                           exclude_cycles=exclude_601)
        selected = select_vcap_cycles(cycle_map_601, step)
        if selected:
            doe_data[doe] = (df_601, selected)

    if not doe_data:
        print("  No cycling data found for " + test_id)
        return

    doe_list = sorted(doe_data.keys())
    n_does   = len(doe_list)
    ncols    = 3
    nrows    = (n_does + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(5 * ncols, 4.5 * nrows),
                             sharex=True, sharey=True)
    fig.patch.set_facecolor("white")
    axes_flat = np.array(axes).flatten()

    for i, doe in enumerate(doe_list):
        ax = axes_flat[i]
        ax.set_facecolor("white")
        ax.grid(True, color="#e0e0e0", linewidth=0.7)
        ax.set_axisbelow(True)

        df_601, selected = doe_data[doe]
        color  = cfg.RUNS.get(doe, {}).get("color", cfg.DEFAULT_COLOR)
        n      = len(selected)
        alphas = np.linspace(0.3, 1.0, n) if n > 1 else [1.0]

        for (actual_cyc, count_1c), alpha in zip(selected, alphas):
            lbl = "Cycle " + str(count_1c)
            v_d, q_d, v_c, q_c = extract_curves(df_601, actual_cyc)
            if q_d is not None:
                ax.plot(q_d, v_d, color=color, lw=1.2, alpha=alpha, label=lbl)
            if q_c is not None:
                ax.plot(q_c, v_c, color=color, lw=1.2, alpha=alpha, ls="--")

        ax.set_title(doe, fontsize=11, fontweight="bold", color=color)
        ax.legend(fontsize=7.5, frameon=False, loc="lower left")
        if i % ncols == 0:
            ax.set_ylabel("Voltage (V)", fontsize=10)
        if i >= ncols * (nrows - 1):
            ax.set_xlabel("Capacity (Ah)", fontsize=10)

    # Hide unused axes; use one spare for legend note
    spare_idx = n_does
    for j in range(n_does, len(axes_flat)):
        axes_flat[j].set_visible(False)

    if spare_idx < len(axes_flat):
        axes_flat[spare_idx].set_visible(True)
        axes_flat[spare_idx].axis("off")
        axes_flat[spare_idx].text(
            0.5, 0.55,
            "Solid = Discharge\nDashed = Charge\n(1C cycle count label)",
            ha="center", va="center", fontsize=10, color="#444",
            transform=axes_flat[spare_idx].transAxes,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#ccc")
        )

    rate_str = cfg.TESTS.get(test_id, {}).get("rate", "1C")
    title = ("Voltage vs Capacity  --  " + test_id
             + "  (" + str(temp_c) + " C)"
             + "  |  every " + str(step) + " " + rate_str + " cycles")
    fig.suptitle(title, fontsize=12, y=1.01)
    plt.tight_layout()

    out = plot_dir / (test_id + "_vcap.png")
    fig.savefig(out, dpi=cfg.PLOT_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  Saved " + out.name)


def main(filter_test=None):
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    if not csv_files:
        print("No CSV files found in data/")
        return

    groups = {}
    for f in csv_files:
        tid = extract_test_id(f.name)
        if tid is None or tid not in cfg.TESTS:
            continue
        if filter_test and tid != filter_test:
            continue
        groups.setdefault(tid, []).append(f)

    for test_id in sorted(groups):
        print("V-cap: " + test_id + " (" + str(len(groups[test_id])) + " files)")
        run_test(test_id, groups[test_id])


if __name__ == "__main__":
    filter_test = sys.argv[1] if len(sys.argv) > 1 else None
    main(filter_test)
