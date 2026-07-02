"""
extract.py - Parse raw cycling CSV files and return tidy DataFrames.
"""
import re
from pathlib import Path
import pandas as pd

_OFF_TIME  = 1
_OFF_VOLT  = 2
_OFF_CURR  = 3
_OFF_CAP   = 4
_OFF_WH    = 5
_OFF_TEMP  = 6


def extract_run_id(filename):
    m = re.search(r'_Test\d+_([^_]+)_', filename, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'_([^_]+)_\d+', filename, re.IGNORECASE)
    return m.group(1) if m else Path(filename).stem


def load_csv(filepath):
    return pd.read_csv(filepath, skiprows=1, low_memory=False)


def extract_cycling_data(df, start_cycle=28, end_cycle=2500, increment=10,
                         rpt_counter_reset=90, rpt_skip=36):
    records = []
    cycle   = start_cycle
    counter = 0
    cols    = df.columns
    while cycle < end_cycle:
        col_str = "_C" + str(cycle) + "_Type"
        matches = [c for c in cols if col_str in c]
        if len(matches) == 1:
            col_data = df[matches[0]]
            col_idx  = cols.get_loc(matches[0])
            # Build list of (positional_index, value) skipping NaN gaps
            non_null = [(i, v) for i, v in enumerate(col_data.values)
                        if isinstance(v, str)]
            for k in range(len(non_null) - 1):
                i, v = non_null[k]
                _, w = non_null[k + 1]
                if v == "CC/D" and w == "CC/R":
                    records.append({
                        "cycle":       cycle,
                        "capacity_ah": df.iat[i, col_idx + _OFF_CAP],
                        "energy_wh":   df.iat[i, col_idx + _OFF_WH],
                        "temperature": df.iat[i, col_idx + _OFF_TEMP],
                    })
                    break
        if counter == rpt_counter_reset:
            cycle   += rpt_skip
            counter  = 0
        else:
            cycle   += increment
            counter += increment
    return pd.DataFrame(records)


def build_cycle_map(df, count_offset=0, current_1c_min=68.0,
                    dis_rows_min=10, dis_rows_max=500,
                    exclude_cycles=None):
    """
    Count cycling discharge cycles (1C or 2C) sequentially, excluding RPT/HPPC.

    Parameters
    ----------
    df             : wide-format cycling DataFrame (skiprows=1)
    count_offset   : starting count (for chaining across files)
    current_1c_min : minimum peak CC/D current (A) to qualify as a cycling cycle
                     Use cfg.CURRENT_1C_MIN (68 A) for 1C, cfg.CURRENT_2C_MIN (138 A) for 2C.
    dis_rows_min   : minimum CC/D row count
    dis_rows_max   : maximum CC/D row count (excludes C/20 with 900+ rows)
    exclude_cycles : set of cycle numbers to skip (RPT block cycles)

    Returns
    -------
    (mapping, final_count)
      mapping     : {actual_cycle_number: cycle_count}
      final_count : pass as count_offset to next file for chaining
    """
    cols    = df.columns
    count   = count_offset
    mapping = {}
    exc     = exclude_cycles or set()

    cyc_nums = sorted({
        int(m.group(1))
        for c in cols
        for m in [re.search(r'_C(\d+)_Type', c)]
        if m
    })

    for cyc in cyc_nums:
        if cyc in exc:
            continue
        col_name = next((c for c in cols if "_C" + str(cyc) + "_Type" in c), None)
        if col_name is None:
            continue
        ci       = cols.get_loc(col_name)
        dis_mask = df[col_name] == "CC/D"
        n_dis    = int(dis_mask.sum())
        if not (dis_rows_min <= n_dis <= dis_rows_max):
            continue
        try:
            max_cur = df.loc[dis_mask].iloc[:, ci + _OFF_CURR].abs().astype(float).max()
        except Exception:
            continue
        if max_cur >= current_1c_min:
            count += 1
            mapping[cyc] = count

    return mapping, count
