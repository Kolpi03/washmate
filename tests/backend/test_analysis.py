"""Tests for analysis/daily_report.py. The rows below are TEST FIXTURES for the validator only,
not project data (data/data.csv is left for real fieldwork)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis"))
import daily_report as dr  # noqa: E402

HEADER = ("observation_id,date,booking_reference,washing_mode,actual_duration_minutes,actual_price,"
          "machine_identifier,start_time,end_time,completion_status,water_usage_litres,payment_status,water_basis\n")


def write(tmp_path, rows):
    p = tmp_path / "t.csv"
    p.write_text(HEADER + "\n".join(rows) + "\n")
    return p


GOOD = ["1,2025-01-10,,Normal Wash,44,30,M1,10:00,10:44,COMPLETED,48,VERIFIED,MEASURED",
        "2,2025-01-10,,Quick Wash,26,20,M2,10:30,10:56,COMPLETED,,VERIFIED,",
        "3,2025-01-10,,Normal Wash,47,30,M1,11:00,11:47,COMPLETED,52,PENDING,ESTIMATED"]


def test_valid_rows_are_analysed(tmp_path):
    rep, issues, _ = dr.run(write(tmp_path, GOOD))
    assert issues == [] and rep["valid_records"] == 3 and rep["completed_sessions"] == 3
    assert rep["most_popular_mode"]["mode"] == "Normal Wash"
    assert rep["total_recorded_revenue_inr"] == 50.0  # PENDING row excluded
    assert rep["average_actual_duration_min"] == pytest.approx(39.0)
    w = rep["water_usage"]
    assert (w["measured_litres"], w["estimated_litres"], w["records_without_water_data"]) == (48, 52, 1)
    assert rep["enough_data"] is False
    assert "WARNING" in dr.render(rep, issues)


def test_detects_every_class_of_bad_row(tmp_path):
    bad = ["4,2025-01-10,,Normal Wash,,30,M1,10:00,10:44,COMPLETED,,VERIFIED,",           # missing duration
           "5,2025-13-45,,Normal Wash,44,30,M1,10:00,10:44,COMPLETED,,VERIFIED,",         # invalid date
           "6,2025-01-10,,Normal Wash,-5,30,M1,10:00,10:44,COMPLETED,,VERIFIED,",         # invalid duration
           "7,2025-01-10,,Normal Wash,44,abc,M1,10:00,10:44,COMPLETED,,VERIFIED,",        # invalid price
           "8,2025-01-10,,Normal Wash,44,30,M1,25:00,10:44,COMPLETED,,VERIFIED,",         # invalid timestamp
           "9,2025-01-10,,Normal Wash,44,30,M1,11:00,10:00,COMPLETED,,VERIFIED,",         # end before start
           "1,2025-01-10,,Normal Wash,44,30,M1,12:00,12:44,COMPLETED,,VERIFIED,",         # duplicate id
           "11,2025-01-10,,Normal Wash,44,30,Z9,13:00,13:44,COMPLETED,,VERIFIED,",        # unknown machine
           "12,2025-01-10,,Normal Wash,44,30,M1,14:00,14:44,COMPLETED,40,VERIFIED,"]      # water without basis
    rep, issues, df = dr.run(write(tmp_path, GOOD + bad), machines=["M1", "M2"])
    rows = {r for r, _ in issues}
    assert rows == set(range(5, 14)) and rep["valid_records"] == 3
    text = " ".join(m for _, m in issues)
    for needle in ("missing required", "invalid date", "invalid duration", "invalid price", "invalid timestamp",
                   "not after", "duplicate observation_id", "incorrect machine", "water_basis"):
        assert needle in text, needle


def test_empty_template_reports_no_data(tmp_path, capsys):
    p = write(tmp_path, [])
    assert dr.main(["--csv", str(p)]) == 0
    assert "No valid records" in capsys.readouterr().out


def test_missing_columns_and_missing_file(tmp_path, capsys):
    p = tmp_path / "bad.csv"
    p.write_text("a,b\n1,2\n")
    assert dr.main(["--csv", str(p)]) == 2
    assert dr.main(["--csv", str(tmp_path / "nope.csv")]) == 2


def test_twenty_plus_records_no_warning_and_peak_hours(tmp_path):
    rows = [f"{i},2025-01-1{i % 5},,Normal Wash,{40 + i % 7},30,M{1 + i % 3},{9 + i % 4:02d}:00,"
            f"{9 + i % 4:02d}:{40 + i % 7},COMPLETED,,VERIFIED," for i in range(1, 25)]
    rep, issues, _ = dr.run(write(tmp_path, rows))
    assert rep["valid_records"] == 24 and rep["enough_data"] and "peak_hours" in rep
    assert "WARNING" not in dr.render(rep, issues)


def test_committed_template_is_header_only_and_runs():
    root = Path(__file__).resolve().parents[2]
    rep, issues, df = dr.run(root / "data" / "data.csv")
    assert rep["valid_records"] == len(df)  # no committed synthetic rows are silently accepted
