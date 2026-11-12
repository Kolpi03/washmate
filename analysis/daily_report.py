#!/usr/bin/env python3
"""Analyse REAL observed laundry records from data/data.csv.

Usage:
    python analysis/daily_report.py [--csv data/data.csv] [--machines M1,M2,...] [--json out.json]

The script never invents data: with an empty/small file it reports exactly what is (not) available.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

REQUIRED = ["observation_id", "date", "washing_mode", "actual_duration_minutes", "actual_price",
            "machine_identifier", "start_time", "end_time", "completion_status", "payment_status"]
OPTIONAL = ["booking_reference", "water_usage_litres", "water_basis"]  # water_basis: MEASURED | ESTIMATED
COMPLETED = {"COMPLETED", "DONE", "FINISHED"}
MIN_RECORDS = 20
MAX_DURATION = 300


def load_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, skipinitialspace=True)
    df.columns = [c.strip().lower() for c in df.columns]
    missing_cols = [c for c in REQUIRED if c not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_cols)}")
    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = ""
    df = df.apply(lambda s: s.str.strip())
    return df[~(df[REQUIRED] == "").all(axis=1)].reset_index(drop=True)  # drop fully blank rows


def validate(df: pd.DataFrame, machines: list[str] | None = None):
    """Return (valid_df, issues). Each issue = (row_number, problem). Row numbers match the CSV file (header = 1)."""
    issues: list[tuple[int, str]] = []
    bad: set[int] = set()

    def flag(i, msg):
        issues.append((i + 2, msg))
        bad.add(i)

    dup_ids = df["observation_id"].duplicated(keep="first")
    dup_rows = df.duplicated(subset=[c for c in df.columns if c != "observation_id"], keep="first")
    machine_ok = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
    known = {m.upper() for m in machines} if machines else None
    parsed = {}
    for i, r in df.iterrows():
        for col in REQUIRED:
            if r[col] == "":
                flag(i, f"missing required field '{col}'")
        if dup_ids[i]:
            flag(i, f"duplicate observation_id '{r['observation_id']}'")
        elif dup_rows[i]:
            flag(i, "duplicate observation (identical to an earlier row)")
        d = pd.to_datetime(r["date"], format="%Y-%m-%d", errors="coerce")
        if r["date"] and pd.isna(d):
            flag(i, f"invalid date '{r['date']}' (use YYYY-MM-DD)")
        elif not pd.isna(d) and d > pd.Timestamp.today().normalize():
            flag(i, f"date '{r['date']}' is in the future")
        dur = pd.to_numeric(r["actual_duration_minutes"], errors="coerce")
        if r["actual_duration_minutes"] and (pd.isna(dur) or dur <= 0 or dur > MAX_DURATION):
            flag(i, f"invalid duration '{r['actual_duration_minutes']}' (must be 1-{MAX_DURATION} minutes)")
        price = pd.to_numeric(r["actual_price"], errors="coerce")
        if r["actual_price"] and (pd.isna(price) or price < 0):
            flag(i, f"invalid price '{r['actual_price']}'")
        water = pd.to_numeric(r["water_usage_litres"], errors="coerce") if r["water_usage_litres"] else None
        if r["water_usage_litres"] and (pd.isna(water) or water < 0):
            flag(i, f"invalid water usage '{r['water_usage_litres']}'")
        if r["water_usage_litres"] and r["water_basis"].upper() not in ("MEASURED", "ESTIMATED"):
            flag(i, "water_usage_litres given but water_basis must be MEASURED or ESTIMATED")
        t0 = pd.to_datetime(r["start_time"], format="%H:%M", errors="coerce")
        t1 = pd.to_datetime(r["end_time"], format="%H:%M", errors="coerce")
        if (r["start_time"] and pd.isna(t0)) or (r["end_time"] and pd.isna(t1)):
            flag(i, "invalid timestamp (use HH:MM, 24-hour)")
        elif not pd.isna(t0) and not pd.isna(t1):
            if t1 <= t0:
                flag(i, "end_time is not after start_time")
            elif not pd.isna(dur) and abs((t1 - t0).total_seconds() / 60 - dur) > 5:
                flag(i, f"duration {dur:g} min does not match start/end ({(t1 - t0).total_seconds() / 60:g} min)")
        m = r["machine_identifier"]
        if m and (not machine_ok.match(m) or (known and m.upper() not in known)):
            flag(i, f"incorrect machine identifier '{m}'" + (f" (expected one of {sorted(known)})" if known else ""))
        parsed[i] = (d, dur, price, water, t0, t1)
    valid = df.drop(index=list(bad)).copy()
    if valid.empty:
        return valid, issues
    valid["date_p"] = pd.to_datetime(valid["date"])
    valid["dur"] = pd.to_numeric(valid["actual_duration_minutes"])
    valid["price"] = pd.to_numeric(valid["actual_price"])
    valid["water"] = pd.to_numeric(valid["water_usage_litres"], errors="coerce")
    valid["start_dt"] = pd.to_datetime(valid["start_time"], format="%H:%M")
    valid["end_dt"] = pd.to_datetime(valid["end_time"], format="%H:%M")
    valid["status_u"] = valid["completion_status"].str.upper()
    valid["pay_u"] = valid["payment_status"].str.upper()
    return valid, issues


def analyse(valid: pd.DataFrame, total_rows: int) -> dict:
    n = len(valid)
    out: dict = {"rows_in_file": total_rows, "valid_records": n, "enough_data": n >= MIN_RECORDS}
    if n == 0:
        return out
    done = valid[valid["status_u"].isin(COMPLETED)]
    out["total_observed_bookings"] = n
    out["completed_sessions"] = int(len(done))
    modes = valid["washing_mode"].str.title().value_counts()
    out["most_popular_mode"] = {"mode": modes.index[0], "count": int(modes.iloc[0])}
    out["mode_counts"] = {k: int(v) for k, v in modes.items()}
    out["average_actual_duration_min"] = round(float(done["dur"].mean()), 1) if len(done) else None
    paid = valid[valid["pay_u"].isin({"VERIFIED", "PAID", "RECEIVED"})]
    out["total_recorded_revenue_inr"] = round(float(paid["price"].sum()), 2)
    out["revenue_note"] = "Sum of prices on rows whose payment_status is VERIFIED/PAID/RECEIVED"
    out["payment_status_summary"] = {k: int(v) for k, v in valid["pay_u"].value_counts().items()}
    w = valid.dropna(subset=["water"])
    out["water_usage"] = {
        "measured_litres": float(w[w["water_basis"].str.upper() == "MEASURED"]["water"].sum()),
        "measured_records": int((w["water_basis"].str.upper() == "MEASURED").sum()),
        "estimated_litres": float(w[w["water_basis"].str.upper() == "ESTIMATED"]["water"].sum()),
        "estimated_records": int((w["water_basis"].str.upper() == "ESTIMATED").sum()),
        "records_without_water_data": int(n - len(w)),
    }
    hours = valid["start_dt"].dt.hour.value_counts().sort_index()
    out["appointments_by_start_hour"] = {f"{h:02d}:00": int(c) for h, c in hours.items()}
    if len(valid) >= 5:
        top = hours.max()
        out["peak_hours"] = [f"{h:02d}:00" for h, c in hours.items() if c == top]
    # utilisation: busy minutes / observed window (first start .. last end that day) per machine, only with >=5 jobs that day
    util = []
    for day, g in valid[valid["status_u"].isin(COMPLETED)].groupby("date"):
        if len(g) < 5:
            continue
        window = (g["end_dt"].max() - g["start_dt"].min()).total_seconds() / 60
        for mach, mg in g.groupby(g["machine_identifier"].str.upper()):
            util.append({"date": day, "machine": mach, "utilization_pct": round(100 * mg["dur"].sum() / window, 1)})
    out["machine_utilization"] = util or "insufficient data (needs >= 5 completed jobs on a day)"
    return out


def render(rep: dict, issues) -> str:
    L = ["=" * 60, "WASHMATE – OBSERVED DATA REPORT", "=" * 60]
    L.append(f"Rows in file: {rep['rows_in_file']} | valid records: {rep['valid_records']} | rejected rows: {len(issues)}")
    if issues:
        L.append("\nData-quality issues (rows excluded from analysis):")
        L += [f"  row {r}: {m}" for r, m in issues]
    if rep["valid_records"] < MIN_RECORDS:
        L.append(f"\n⚠ WARNING: only {rep['valid_records']} valid record(s); at least {MIN_RECORDS} real observations are "
                 "required. Treat any figures below as indicative only.")
    if rep["valid_records"] == 0:
        L.append("\nNo valid records – nothing to analyse.")
        return "\n".join(L)
    L += ["", f"Total observed bookings : {rep['total_observed_bookings']}",
          f"Completed sessions      : {rep['completed_sessions']}",
          f"Most popular mode       : {rep['most_popular_mode']['mode']} ({rep['most_popular_mode']['count']} bookings)",
          f"Avg actual duration     : {rep['average_actual_duration_min']} min (completed sessions only)",
          f"Total recorded revenue  : ₹{rep['total_recorded_revenue_inr']:g}  [{rep['revenue_note']}]"]
    w = rep["water_usage"]
    L += ["", "Water usage (kept separate):",
          f"  MEASURED  : {w['measured_litres']:g} L over {w['measured_records']} record(s)",
          f"  ESTIMATED : {w['estimated_litres']:g} L over {w['estimated_records']} record(s)",
          f"  no water data: {w['records_without_water_data']} record(s)"]
    L += ["", "Payment status: " + ", ".join(f"{k}={v}" for k, v in rep["payment_status_summary"].items()),
          "Mode counts   : " + ", ".join(f"{k}={v}" for k, v in rep["mode_counts"].items()),
          "By start hour : " + ", ".join(f"{k}→{v}" for k, v in rep["appointments_by_start_hour"].items())]
    L.append("Peak period(s): " + (", ".join(rep["peak_hours"]) if "peak_hours" in rep else "insufficient data (needs >= 5 records)"))
    mu = rep["machine_utilization"]
    if isinstance(mu, str):
        L.append("Machine utilisation: " + mu)
    else:
        L.append("Machine utilisation (busy time / observed window that day):")
        L += [f"  {u['date']} {u['machine']}: {u['utilization_pct']}%" for u in mu]
    return "\n".join(L)


def run(csv_path, machines=None):
    df = load_csv(csv_path)
    valid, issues = validate(df, machines)
    rep = analyse(valid, len(df))
    return rep, issues, df


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(root / "data" / "data.csv"))
    ap.add_argument("--machines", help="comma-separated valid machine identifiers (e.g. M1,M2,M3)")
    ap.add_argument("--json", help="also write the report as JSON")
    a = ap.parse_args(argv)
    try:
        rep, issues, _ = run(a.csv, a.machines.split(",") if a.machines else None)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(render(rep, issues))
    if a.json:
        Path(a.json).write_text(json.dumps({"report": rep, "issues": issues}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
