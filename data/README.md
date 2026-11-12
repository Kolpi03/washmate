# data/data.csv – how to collect it

`data.csv` is intentionally **empty (header only)**. It must be filled with **at least 20 real observations** that you
personally record at the hostel laundry area (stopwatch + the operator's own notebook). Do **not** generate, round-off,
copy or download records – `analysis/daily_report.py` will flag implausible rows but cannot prove authenticity.

| column | what to write |
|---|---|
| observation_id | 1, 2, 3 … (unique) |
| date | `YYYY-MM-DD` of the observation |
| booking_reference | the operator's own booking/serial mark if any, else blank |
| washing_mode | the mode name the operator/student used (as spoken) |
| actual_duration_minutes | stopwatch-measured wash time, whole minutes |
| actual_price | rupees actually charged |
| machine_identifier | the label on the machine (e.g. `M1`) |
| start_time / end_time | 24-hour `HH:MM` read off your phone clock |
| completion_status | `COMPLETED`, `CANCELLED`, `NO_SHOW` … |
| water_usage_litres | only if you **measured** it (bucket/metre) or the operator **stated** an estimate; else blank |
| payment_status | `VERIFIED`/`PAID` if money was received, `PENDING`, `REFUNDED` … |
| water_basis | `MEASURED` or `ESTIMATED` (required when water_usage_litres is filled) |

Run the analysis: `python analysis/daily_report.py` (add `--machines M1,M2,M3` to check machine labels).
