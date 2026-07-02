from __future__ import annotations
import re
import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from extract import load_csv  # noqa: E402
import config_template as ct  # noqa: E402
from defaults import PALETTE  # noqa: E402

_FN = re.compile(
    r"^(?P<date>\d{6})_(?P<chem>[A-Za-z0-9]+)_(?P<test>Test\d+)_(?P<doe>DOE\d+)_(?P<temp>\d+)",
    re.IGNORECASE,
)


def parse_filename(name: str) -> dict | None:
    m = _FN.match(name)
    if not m:
        return None
    return {
        "date": m.group("date"),
        "chem": m.group("chem"),
        "test": m.group("test"),
        "doe": m.group("doe"),
        "temp_c": int(m.group("temp")),
    }


def infer_c_rate(df) -> str | None:
    """Peak |CC/D| current decides rate: >=2C threshold -> 2C, >=1C -> 1C."""
    cols = df.columns
    peak = 0.0
    for c in cols:
        if "_Type" not in c:
            continue
        ci = cols.get_loc(c)
        mask = df[c] == "CC/D"
        if not mask.any():
            continue
        try:
            cur = df.loc[mask].iloc[:, ci + 3].abs().astype(float).max()
            peak = max(peak, float(cur))
        except Exception:
            continue
    if peak >= ct.CURRENT_2C_MIN:
        return "2C"
    if peak >= ct.CURRENT_1C_MIN:
        return "1C"
    return None


def discover(data_dir: Path) -> dict:
    tests: dict = {}
    # group files by test
    by_test: dict = {}
    for f in sorted(Path(data_dir).glob("*.csv")):
        meta = parse_filename(f.name)
        if not meta:
            continue
        by_test.setdefault(meta["test"], []).append((f, meta))
    for test, items in by_test.items():
        does = sorted({m["doe"] for _, m in items}, key=lambda s: int(s[3:]))
        temp_c = items[0][1]["temp_c"]
        # infer rate from the largest cycling file (most data)
        rate = None
        for f, _ in sorted(items, key=lambda x: x[0].stat().st_size, reverse=True):
            try:
                rate = infer_c_rate(load_csv(f))
            except Exception:
                rate = None
            if rate:
                break
        tests[test] = {"temp_c": temp_c, "rate": rate or "1C", "does": does}
    return tests


def build_config(discovered: dict, overrides: dict) -> dict:
    ov_tests = (overrides or {}).get("tests", {})
    ov_groups = (overrides or {}).get("groups", [])
    ov_colors = (overrides or {}).get("colors", {})

    tests: dict = {}
    runs: dict = {}
    groups: list = []
    palette = PALETTE
    color_i = 0

    for test, info in discovered.items():
        if ov_tests.get(test, {}).get("include") is False:
            continue
        rate = ov_tests.get(test, {}).get("rate") or info["rate"]
        tests[test] = {"temp_c": info["temp_c"], "rate": rate,
                       "color": palette[color_i % len(palette)]}
        color_i += 1
        for doe in info["does"]:
            if doe not in runs:
                oc = ov_colors.get(doe, {})
                runs[doe] = {
                    "label": oc.get("label") or doe,
                    "color": oc.get("color") or palette[color_i % len(palette)],
                    "marker": "o",
                }
                color_i += 1
        test_groups = [g for g in ov_groups if g.get("test") == test]
        if test_groups:
            for g in test_groups:
                groups.append({"does": g["does"],
                               "reference": g.get("reference", g["does"][0])})
        else:
            groups.append({"does": list(info["does"]),
                           "reference": info["does"][0] if info["does"] else None})
    return {"tests": tests, "runs": runs, "doe_groups": groups}


def read_sheet_overrides(sheet_id: str | None, creds) -> dict:
    if not sheet_id:
        return {}
    from googleapiclient.discovery import build
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    values = svc.spreadsheets().values()
    out: dict = {"tests": {}, "groups": [], "colors": {}}

    def rows(tab):
        try:
            return values.get(spreadsheetId=sheet_id, range=tab).execute().get("values", [])
        except Exception:
            return []

    for r in rows("Tests")[1:]:
        if not r:
            continue
        test = r[0].strip()
        rate = r[1].strip() if len(r) > 1 and r[1].strip() else None
        include = not (len(r) > 2 and r[2].strip().lower() in ("no", "false", "0"))
        out["tests"][test] = {"rate": rate, "include": include}
    for r in rows("DOE Groups")[1:]:
        if len(r) < 3 or not r[0].strip():
            continue
        does = [d.strip() for d in r[2].split(",") if d.strip()]
        out["groups"].append({"test": r[0].strip(),
                              "reference": (r[3].strip() if len(r) > 3 and r[3].strip() else (does[0] if does else None)),
                              "does": does})
    for r in rows("DOE Colors")[1:]:
        if not r or not r[0].strip():
            continue
        out["colors"][r[0].strip()] = {
            "color": r[1].strip() if len(r) > 1 else None,
            "label": r[2].strip() if len(r) > 2 else None,
        }
    return out
