# run_dqdv.py -- dQ/dV plots: C/20 then all C/10 RPT blocks, per test
#
# Structure matches vCap: one PNG per test, subplots per DOE.
# Per DOE subplot:
#   Solid line       : C/20 from formation file (260526, cycle 2)
#   Dashed lines     : C/10 RPT blocks from cycling file (260601, cycles 2/128/254)
#                      Alpha fades from 1.0 (first) to 0.3 (last)
# Two output files per test: <test>_dqdv_charge.png, <test>_dqdv_discharge.png
#
# Usage:
#   python run_dqdv.py          # all tests
#   python run_dqdv.py Test4    # one test only

import sys
import re
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from scipy.signal import savgol_filter

import config as cfg
from extract import load_csv

from paths import DATA_DIR, OUT_DIR as OUT_BASE
RPT_INTERVAL = 126


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


def get_curves(df, cyc):
    cols = df.columns
    m = [c for c in cols if "_C" + str(cyc) + "_Type" in c]
    if not m:
        return None, None, None, None
    ci  = cols.get_loc(m[0])
    tc  = df[m[0]]
    dis = tc == "CC/D"
    chg = tc.isin(["CC/C", "CC/CV/C"])
    v_d = df.loc[dis].iloc[:, ci + 2].astype(float).values if dis.sum() > 20 else None
    q_d = df.loc[dis].iloc[:, ci + 4].astype(float).values if dis.sum() > 20 else None
    v_c = df.loc[chg].iloc[:, ci + 2].astype(float).values if chg.sum() > 20 else None
    q_c = df.loc[chg].iloc[:, ci + 4].astype(float).values if chg.sum() > 20 else None
    return v_d, q_d, v_c, q_c


def compute_dqdv(v, q):
    w = cfg.DQDV_SMOOTH_WINDOW
    p = cfg.DQDV_SMOOTH_POLY
    n = cfg.DQDV_GRID_POINTS
    try:
        order = np.argsort(v)
        vs = v[order]; qs = q[order]
        _, idx = np.unique(vs, return_index=True)
        vs = vs[idx]; qs = qs[idx]
        if len(vs) < w + 2:
            return None, None
        v_grid = np.linspace(vs[0], vs[-1], n)
        q_i    = np.interp(v_grid, vs, qs)
        q_sm   = savgol_filter(q_i, window_length=w, polyorder=p)
        dq     = np.gradient(q_sm, v_grid)
        return v_grid, savgol_filter(dq, window_length=w, polyorder=p)
    except Exception:
        return None, None


def load_test_files(test_id):
    formation = {}
    cycling   = {}
    for fpath in sorted(DATA_DIR.glob("*.csv")):
        if extract_test_id(fpath.name) != test_id:
            continue
        doe = extract_run_id(fpath.name)
        try:
            df = load_csv(fpath)
        except Exception:
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
    plot_dir = OUT_BASE / test_id / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    test_cfg = cfg.TESTS.get(test_id, {})
    temp_c   = test_cfg.get("temp_c", "?")

    doe_files = load_test_files(test_id)
    if not doe_files:
        print("  No files for " + test_id)
        return

    # Order DOEs same as config groups
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

    n_does = len(doe_order)
    if n_does == 0:
        return

    ncols = 3
    nrows = (n_does + ncols - 1) // ncols

    for mode in ("charge", "discharge"):
        fig, axes = plt.subplots(nrows, ncols,
                                 figsize=(5.5 * ncols, 4.5 * nrows))
        fig.patch.set_facecolor("white")
        axes_flat = np.array(axes).flatten()

        for i, doe in enumerate(doe_order):
            ax = axes_flat[i]
            ax.set_facecolor("white")
            ax.grid(True, color="#e0e0e0", linewidth=0.7)
            ax.set_axisbelow(True)

            color  = cfg.RUNS.get(doe, {}).get("color", cfg.DEFAULT_COLOR)
            entry  = doe_files[doe]

            # C/20 from formation file (solid)
            df_f = entry["formation"]
            if df_f is not None:
                v_d, q_d, v_c, q_c = get_curves(df_f, 2)
                arr_v = v_c if mode == "charge" else v_d
                arr_q = q_c if mode == "charge" else q_d
                if arr_v is not None:
                    vg, dq = compute_dqdv(arr_v, arr_q)
                    if vg is not None:
                        ax.plot(vg, dq, color=color, lw=2.0, alpha=1.0,
                                ls="-", label="C/20")

            # C/10 RPT blocks from cycling file (dashed, fading)
            df_c = entry["cycling"]
            if df_c is not None:
                rpt_cycs = []
                for k in range(100):
                    cyc = 2 + k * RPT_INTERVAL
                    if any("_C" + str(cyc) + "_Type" in c for c in df_c.columns):
                        rpt_cycs.append(cyc)
                    else:
                        break
                n_rpt  = len(rpt_cycs)
                alphas = np.linspace(1.0, 0.3, n_rpt) if n_rpt > 1 else [1.0]
                for j, (cyc, alpha) in enumerate(zip(rpt_cycs, alphas)):
                    v_d, q_d, v_c, q_c = get_curves(df_c, cyc)
                    arr_v = v_c if mode == "charge" else v_d
                    arr_q = q_c if mode == "charge" else q_d
                    if arr_v is not None:
                        vg, dq = compute_dqdv(arr_v, arr_q)
                        if vg is not None:
                            ax.plot(vg, dq, color=color, lw=1.4,
                                    alpha=alpha, ls="--",
                                    label="C/10 Blk" + str(j + 1))

            ax.set_title(doe, fontsize=11, fontweight="bold", color=color)
            ax.legend(fontsize=7.5, frameon=False, loc="best")
            if i % ncols == 0:
                ax.set_ylabel("dQ/dV (Ah/V)", fontsize=10)
            if i >= ncols * (nrows - 1):
                ax.set_xlabel("Voltage (V)", fontsize=10)

        # Hide unused axes
        for j in range(n_does, len(axes_flat)):
            axes_flat[j].set_visible(False)

        # Use spare panel for legend note if available
        if n_does < len(axes_flat):
            sp = axes_flat[n_does]
            sp.set_visible(True)
            sp.axis("off")
            sp.text(0.5, 0.5,
                    "Solid = C/20 (formation)\nDashed = C/10 RPT blocks\n(alpha fades with age)",
                    ha="center", va="center", fontsize=10, color="#444",
                    transform=sp.transAxes,
                    bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#ccc"))

        title = ("dQ/dV  " + mode.capitalize() + "  --  " + test_id
                 + "  (" + str(temp_c) + " C)")
        fig.suptitle(title, fontsize=12, y=1.01)
        plt.tight_layout()

        mode_short = "chg" if mode == "charge" else "dis"
        out = plot_dir / (test_id + "_dqdv_" + mode_short + ".png")
        fig.savefig(out, dpi=cfg.PLOT_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print("  Saved " + out.name)


def main(filter_test=None):
    tests = sorted(cfg.TESTS.keys()) if filter_test is None else [filter_test]
    for tid in tests:
        print("\n--- dQ/dV: " + tid + " ---")
        run_test(tid)


if __name__ == "__main__":
    filter_test = sys.argv[1] if len(sys.argv) > 1 else None
    main(filter_test)
