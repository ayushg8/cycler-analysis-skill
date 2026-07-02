# run_rpt.py  --  Extract RPT data and write per-test vertical CSV
#
# Cycle labels use total 1C (or 2C for Test5) count carried across files:
#   Cycle 0 = formation RPT from 260526 file (C/20 caps fill <=C/10 columns)
#   Cycle N = RPT blocks in 260601/260602 file (C/10 caps fill <=C/10 columns)
#
# Columns: Cycle | <=C/10 Chg (Ah) | <=C/10 Dis (Ah) | Dis IR 1-12 | Ch IR 1-11
# C/2 capacities are not included in the output.
#
# Usage:
#   python run_rpt.py          # all tests in config.TESTS
#   python run_rpt.py Test4    # one test only

import sys
import re
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import config as cfg
from extract import load_csv, build_cycle_map
from extract_rpt import extract_rpt_data_c20, extract_rpt_data_c10

from paths import DATA_DIR, OUT_DIR as OUT_BASE
RPT_INTERVAL = 126

_C10_RPT_SPAN = 26
_C20_RPT_SPAN = 27


# ---------- File helpers ------------------------------------------------------

def extract_run_id(filename):
    m = re.search(r"_Test\d+_([^_]+)_", filename, re.IGNORECASE)
    return m.group(1) if m else Path(filename).stem


def extract_test_id(filename):
    m = re.search(r"_(Test\d+)_", filename, re.IGNORECASE)
    return m.group(1) if m else None


def c2_dis_rows(df):
    cols = df.columns
    m = [c for c in cols if "_C2_Type" in c]
    return (df[m[0]] == "CC/D").sum() if m else 0


def is_formation_file(df):
    return c2_dis_rows(df) > 900


def count_rpt_blocks(df):
    cols  = df.columns
    count = 0
    for rpt in range(0, 4000, RPT_INTERVAL):
        if any("_C" + str(2 + rpt) + "_Type" in c for c in cols):
            count += 1
        else:
            break
    return count


def load_doe_files(test_id):
    groups = {}
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
            score = c2_dis_rows(df)
            prev  = groups.get(doe, {}).get("formation")
            if prev is None or score > prev[1]:
                groups.setdefault(doe, {})["formation"] = (df, score)
        else:
            score = count_rpt_blocks(df)
            if score == 0:
                continue
            prev = groups.get(doe, {}).get("cycling")
            if prev is None or score > prev[1]:
                groups.setdefault(doe, {})["cycling"] = (df, score)
    return {
        doe: {
            "formation": cats.get("formation", (None,))[0],
            "cycling":   cats.get("cycling",   (None,))[0],
        }
        for doe, cats in groups.items()
    }


# ---------- Cycle-rate helpers ------------------------------------------------

def get_current_min(test_id):
    rate = cfg.TESTS.get(test_id, {}).get("rate", "1C")
    return cfg.CURRENT_2C_MIN if rate == "2C" else cfg.CURRENT_1C_MIN


def get_rpt_exclude_cycles_c10(df):
    exclude = set()
    cols    = df.columns
    for k in range(0, 100):
        start = 2 + k * RPT_INTERVAL
        if not any("_C" + str(start) + "_Type" in c for c in cols):
            break
        for cyc in range(start, start + _C10_RPT_SPAN):
            exclude.add(cyc)
    return exclude


# ---------- 1C/2C cycle counting ---------------------------------------------

def get_offset(df_526, current_min):
    if df_526 is None:
        return 0
    _, count = build_cycle_map(df_526, count_offset=0, current_1c_min=current_min)
    return count


def rpt_cycle_labels(df_601, offset, current_min):
    exclude      = get_rpt_exclude_cycles_c10(df_601)
    cycle_map, _ = build_cycle_map(df_601, count_offset=0,
                                   current_1c_min=current_min,
                                   exclude_cycles=exclude)
    labels = []
    for i in range(0, 4000 // RPT_INTERVAL + 1):
        rpt_cyc = 2 + i * RPT_INTERVAL
        if not any("_C" + str(rpt_cyc) + "_Type" in c for c in df_601.columns):
            break
        count_before = sum(1 for cyc in cycle_map if cyc < rpt_cyc)
        labels.append(offset + count_before)
    return labels


# ---------- RPT extraction ----------------------------------------------------

# Columns: <=C/10 Chg, <=C/10 Dis, 12 dis IR, 11 chg IR
_DATA_COLS = (
    ["lte_c10_chg_ah", "lte_c10_dis_ah"]
    + ["dis_ir_" + str(i) for i in range(1, 13)]
    + ["ch_ir_" + str(i)  for i in range(1, 12)]
)

_CSV_HEADERS = (
    ["Cycle", "<=C/10 Chg (Ah)", "<=C/10 Dis (Ah)"]
    + ["Dis IR " + str(i) + " (mOhm)" for i in range(1, 13)]
    + ["Ch IR " + str(i) + " (mOhm)"  for i in range(1, 12)]
)


def build_rpt_table(doe_files, test_id):
    current_min = get_current_min(test_id)
    tables      = {}

    for doe, files in doe_files.items():
        rows   = []
        df_526 = files["formation"]
        df_601 = files["cycling"]

        # 260526 -> Cycle 0: C/20 fills <=C/10 columns
        if df_526 is not None:
            try:
                rpt = extract_rpt_data_c20(df_526, rpt_max_counter=0)
                if not rpt.empty:
                    r   = rpt.iloc[0]
                    row = {"cycle_label": 0}
                    row["lte_c10_chg_ah"] = r.get("c20_chg_ah")
                    row["lte_c10_dis_ah"] = r.get("c20_dis_ah")
                    for i in range(1, 13):
                        row["dis_ir_" + str(i)] = r.get("dis_ir_" + str(i))
                    for i in range(1, 12):
                        row["ch_ir_" + str(i)]  = r.get("ch_ir_" + str(i))
                    rows.append(row)
            except Exception as e:
                print("  WARNING 526 extract [" + doe + "]: " + str(e))

        # 260601/260602 -> Cycle N: C/10 fills <=C/10 columns
        offset = get_offset(df_526, current_min)
        if df_601 is not None:
            try:
                labels = rpt_cycle_labels(df_601, offset, current_min)
                rpt    = extract_rpt_data_c10(df_601, rpt_max_counter=4000)
                for lbl, (_, r) in zip(labels, rpt.iterrows()):
                    row = {"cycle_label": lbl}
                    row["lte_c10_chg_ah"] = r.get("c10_chg_ah")
                    row["lte_c10_dis_ah"] = r.get("c10_dis_ah")
                    for i in range(1, 13):
                        row["dis_ir_" + str(i)] = r.get("dis_ir_" + str(i))
                    for i in range(1, 12):
                        row["ch_ir_" + str(i)]  = r.get("ch_ir_" + str(i))
                    rows.append(row)
            except Exception as e:
                print("  WARNING 601 extract [" + doe + "]: " + str(e))

        tables[doe] = sorted(rows, key=lambda x: x["cycle_label"])

    return tables


# ---------- Comparison rows ---------------------------------------------------

def _pct(value, reference):
    try:
        v = float(value); r = float(reference)
        if r == 0:
            return ""
        return str(round(v / r * 100)) + "%"
    except (TypeError, ValueError):
        return ""


def get_reference_doe(doe):
    for grp in cfg.DOE_GROUPS:
        if doe in grp["does"]:
            return grp["reference"]
    return doe


def build_comparison_rows(tables):
    comparisons = {}
    for doe, rows in tables.items():
        if not rows:
            continue
        ref_doe  = get_reference_doe(doe)
        ref_rows = tables.get(ref_doe, [])
        row0_self = next((r for r in rows if r["cycle_label"] == 0), None)
        row0_ref  = next((r for r in ref_rows if r["cycle_label"] == 0), None)
        row_last  = rows[-1]
        last_lbl  = row_last["cycle_label"]
        vs_ref = []
        if row0_self and row0_ref:
            for col in _DATA_COLS:
                vs_ref.append(_pct(row0_self.get(col), row0_ref.get(col)))
        last_vs_first = []
        if row0_self:
            for col in _DATA_COLS:
                last_vs_first.append(_pct(row_last.get(col), row0_self.get(col)))
        comparisons[doe] = {
            "vs_ref_label":  "vs " + ref_doe + " | Cycle 0",
            "vs_ref":        vs_ref,
            "last_label":    "Cycle " + str(last_lbl) + " vs Cycle 0",
            "last_vs_first": last_vs_first,
        }
    return comparisons


# ---------- CSV writer --------------------------------------------------------

def _fmt(v):
    if v is None:
        return ""
    try:
        f = float(v)
        return "" if str(f) == "nan" else str(f)
    except (TypeError, ValueError):
        return str(v)


def save_rpt_csv(tables, comparisons, out_path):
    lines     = []
    doe_order = []
    seen      = set()
    for grp in cfg.DOE_GROUPS:
        for doe in grp["does"]:
            if doe in tables and doe not in seen:
                doe_order.append(doe)
                seen.add(doe)
    for doe in sorted(tables.keys()):
        if doe not in seen:
            doe_order.append(doe)

    for doe in doe_order:
        rows = tables.get(doe)
        if not rows:
            continue
        comp    = comparisons.get(doe, {})
        ref_doe = get_reference_doe(doe)
        lines.append(doe)
        lines.append(",".join(_CSV_HEADERS))
        for row in rows:
            cells = [str(row["cycle_label"])]
            for col in _DATA_COLS:
                cells.append(_fmt(row.get(col)))
            lines.append(",".join(cells))
        if doe != ref_doe and comp.get("vs_ref"):
            lines.append(comp["vs_ref_label"] + "," + ",".join(comp["vs_ref"]))
        if comp.get("last_vs_first"):
            lines.append(comp["last_label"] + "," + ",".join(comp["last_vs_first"]))
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("  Saved " + out_path.name)


# ---------- Per-test runner ---------------------------------------------------

def run_test(test_id):
    csv_dir = OUT_BASE / test_id / "csv"
    print("  Loading files...")
    doe_files = load_doe_files(test_id)
    if not doe_files:
        print("  No files found for " + test_id)
        return
    print("  DOEs: " + str(sorted(doe_files.keys())))
    print("  Extracting RPT data...")
    tables = build_rpt_table(doe_files, test_id)
    print("  Computing comparison rows...")
    comparisons = build_comparison_rows(tables)
    out_path = csv_dir / "rpt_all_DOEs.csv"
    save_rpt_csv(tables, comparisons, out_path)


def main(filter_test=None):
    tests = sorted(cfg.TESTS.keys()) if filter_test is None else [filter_test]
    for tid in tests:
        print("\n--- RPT extraction: " + tid + " ---")
        run_test(tid)


if __name__ == "__main__":
    filter_test = sys.argv[1] if len(sys.argv) > 1 else None
    main(filter_test)
