"""
extract_rpt.py - Extract RPT block data from wide-format cycling CSVs.

260526  -> C/20 RPT  (extract_rpt_data_c20)
  cycle  2+rpt : C/20 chg (CC/C last row) + C/20 dis (CC/D last row)
  cycle  4+rpt : C/2  chg (CC/CV/C last row) + C/2 dis (CC/D last row)
  cycles  6-17+rpt : 12 discharge HPPC IR pulses
  cycles 18-28+rpt : 11 charge HPPC IR pulses

260601/260602 -> C/10 RPT  (extract_rpt_data_c10)
  cycle  2+rpt : C/10 chg (CC/CV/C last row) + C/10 dis (CC/D last row)
  cycles  4-15+rpt : 12 discharge HPPC IR pulses
  cycles 16-26+rpt : 11 charge HPPC IR pulses

NOTE: _step_capacity returns the LAST row of the given step_type anywhere
in the cycle column (not just the first contiguous block). This correctly
handles multi-segment discharges with rest steps in between.

DCIR: each pulse has 12 rows (row 0 = pre-pulse at I=0, rows 1-11 = 1C pulse).
  Discharge: DCIR = (V0 - V11) / I11 * 1000  (sign=+1)
  Charge:    DCIR = (V11 - V0) / I11 * 1000  (sign=-1)
  Pulses with fewer than 12 rows are skipped (return None).
"""

import pandas as pd


def _find_col(cols, cycle):
    col_str = "_C" + str(cycle) + "_Type"
    matches = [c for c in cols if col_str in c]
    return matches[0] if len(matches) == 1 else None


def _step_capacity(df, cols, cycle, step_type):
    col_name = _find_col(cols, cycle)
    if col_name is None:
        return None
    col_data = df[col_name]
    col_idx  = cols.get_loc(col_name)
    n        = len(col_data)
    last_row = None
    for row in range(n):
        if col_data.iat[row] == step_type:
            last_row = row
    if last_row is None:
        return None
    try:
        return round(float(df.iat[last_row, col_idx + 4]), 3)
    except (ValueError, TypeError):
        return None


def _ir_pulse(df, cols, cycle, step_type, sign):
    col_name = _find_col(cols, cycle)
    if col_name is None:
        return None
    col_data = df[col_name]
    col_idx  = cols.get_loc(col_name)
    n        = len(col_data)
    for row in range(n - 14):
        if (col_data.iat[row] == step_type
                and col_data.iat[row + 11] == step_type
                and col_data.iat[row + 13] == "CC/R"):
            try:
                v0 = float(df.iat[row,      col_idx + 2])
                v1 = float(df.iat[row + 11, col_idx + 2])
                i1 = float(df.iat[row + 11, col_idx + 3])
                if i1 == 0:
                    return None
                return round(sign * (v0 - v1) * 1000 / i1, 4)
            except (ValueError, TypeError):
                return None
    return None


def extract_rpt_data_c20(df, rpt_interval=126, rpt_max_counter=2000):
    cols        = df.columns
    records     = []
    rpt_counter = 0
    block_num   = 0

    while rpt_counter <= rpt_max_counter:
        base_cycle = 2 + rpt_counter
        if _find_col(cols, base_cycle) is None:
            break

        record = {"rpt_block": block_num, "cycle": base_cycle}

        record["c20_chg_ah"] = _step_capacity(df, cols, 2 + rpt_counter, "CC/C")
        record["c20_dis_ah"] = _step_capacity(df, cols, 2 + rpt_counter, "CC/D")
        record["c2_chg_ah"]  = _step_capacity(df, cols, 4 + rpt_counter, "CC/CV/C")
        record["c2_dis_ah"]  = _step_capacity(df, cols, 4 + rpt_counter, "CC/D")

        # 12 discharge HPPC SOC levels: cycles 6-17
        for i, cyc in enumerate(range(6 + rpt_counter, 18 + rpt_counter), start=1):
            record["dis_ir_" + str(i)] = _ir_pulse(df, cols, cyc, "CC/D", +1)

        # 11 charge HPPC SOC levels: cycles 18-28
        for i, cyc in enumerate(range(18 + rpt_counter, 29 + rpt_counter), start=1):
            record["ch_ir_" + str(i)] = _ir_pulse(df, cols, cyc, "CC/C", -1)

        records.append(record)
        rpt_counter += rpt_interval
        block_num   += 1

    return pd.DataFrame(records)


def extract_rpt_data_c10(df, rpt_interval=126, rpt_max_counter=2000):
    cols        = df.columns
    records     = []
    rpt_counter = 0
    block_num   = 0

    while rpt_counter <= rpt_max_counter:
        base_cycle = 2 + rpt_counter
        if _find_col(cols, base_cycle) is None:
            break

        record = {"rpt_block": block_num, "cycle": base_cycle}

        record["c10_chg_ah"] = _step_capacity(df, cols, 2 + rpt_counter, "CC/CV/C")
        record["c10_dis_ah"] = _step_capacity(df, cols, 2 + rpt_counter, "CC/D")

        # 12 discharge HPPC SOC levels: cycles 4-15
        for i, cyc in enumerate(range(4 + rpt_counter, 16 + rpt_counter), start=1):
            record["dis_ir_" + str(i)] = _ir_pulse(df, cols, cyc, "CC/D", +1)

        # 11 charge HPPC SOC levels: cycles 16-26
        for i, cyc in enumerate(range(16 + rpt_counter, 27 + rpt_counter), start=1):
            record["ch_ir_" + str(i)] = _ir_pulse(df, cols, cyc, "CC/C", -1)

        records.append(record)
        rpt_counter += rpt_interval
        block_num   += 1

    return pd.DataFrame(records)


# Backward-compatibility alias
extract_rpt_data = extract_rpt_data_c10
