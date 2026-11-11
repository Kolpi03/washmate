from flask import current_app, g

from app.extensions import db
from app.models import SystemSetting
from app.utils.common import ApiError, parse_time

# key -> (default, type). Illustrative initial values: the operator edits them in Settings.
DEFAULTS = {
    "open_time": ("08:00", "time"),
    "close_time": ("20:00", "time"),
    "slot_interval_minutes": ("30", "int"),
    "turnaround_buffer_minutes": ("10", "int"),
    "grace_period_minutes": ("10", "int"),
    "reservation_hold_minutes": ("15", "int"),
    "reminder_minutes_before": ("15", "int"),
    "student_cancel_cutoff_minutes": ("60", "int"),
    "max_advance_days": ("7", "int"),
    "upi_id": ("", "str"),
    "upi_qr_code_url": ("", "str"),
    "hostel_name": ("NIT Rourkela Hostel", "str"),
}
PUBLIC_KEYS = ("open_time", "close_time", "slot_interval_minutes", "grace_period_minutes",
               "reservation_hold_minutes", "reminder_minutes_before", "student_cancel_cutoff_minutes",
               "max_advance_days", "upi_id", "upi_qr_code_url", "hostel_name", "turnaround_buffer_minutes")


def _load():
    vals = {k: v[0] for k, v in DEFAULTS.items()}
    vals["upi_id"] = current_app.config.get("DEFAULT_UPI_ID", "") or ""
    vals["upi_qr_code_url"] = current_app.config.get("DEFAULT_UPI_QR", "") or ""
    for row in SystemSetting.query.all():
        if row.setting_key in DEFAULTS:
            vals[row.setting_key] = row.setting_value
    return vals


def all_settings():
    if "settings_cache" not in g:
        g.settings_cache = _load()
    return g.settings_cache


def get_int(key):
    return int(all_settings()[key])


def get_str(key):
    return all_settings()[key]


def get_time(key):
    return parse_time(all_settings()[key], key)


def update_settings(data: dict):
    for key, raw in data.items():
        if key not in DEFAULTS:
            raise ApiError(f"Unknown setting '{key}'")
        typ = DEFAULTS[key][1]
        val = str(raw).strip()
        if typ == "int":
            try:
                n = int(val)
            except ValueError:
                raise ApiError(f"{key} must be a whole number")
            if n < 0 or (key in ("slot_interval_minutes", "max_advance_days") and n < 1):
                raise ApiError(f"{key} is out of range")
            val = str(n)
        elif typ == "time":
            val = parse_time(val, key).strftime("%H:%M")
        row = SystemSetting.query.filter_by(setting_key=key).first()
        if row:
            row.setting_value = val
        else:
            db.session.add(SystemSetting(setting_key=key, setting_value=val))
    db.session.flush()
    g.pop("settings_cache", None)
    s = all_settings()
    if s["open_time"] >= s["close_time"]:
        db.session.rollback()
        g.pop("settings_cache", None)
        raise ApiError("open_time must be earlier than close_time")
