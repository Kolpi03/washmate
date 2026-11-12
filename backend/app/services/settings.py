import re

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


LIMITS = {"slot_interval_minutes": (1, 240), "turnaround_buffer_minutes": (0, 240), "grace_period_minutes": (0, 240),
          "reservation_hold_minutes": (1, 240), "reminder_minutes_before": (1, 1440),
          "student_cancel_cutoff_minutes": (0, 1440), "max_advance_days": (1, 60)}
UPI_RE = re.compile(r"^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9.-]{1,40}$")


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
            lo, hi = LIMITS.get(key, (0, 100000))
            if not lo <= n <= hi:
                raise ApiError(f"{key} must be between {lo} and {hi}")
            val = str(n)
        elif typ == "time":
            val = parse_time(val, key).strftime("%H:%M")
        else:
            if len(val) > 500:
                raise ApiError(f"{key} is too long")
            if key == "upi_id" and val and not UPI_RE.match(val):
                raise ApiError("UPI ID must look like name@bank")
            if key == "upi_qr_code_url" and val and not re.match(r"^https?://[^\s]+$", val, re.I):
                raise ApiError("QR code URL must start with http:// or https://")
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
