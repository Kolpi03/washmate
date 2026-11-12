"""Time helpers and shared error type. Always call `now_local()` via this module (tests patch it)."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app, request


class ApiError(Exception):
    def __init__(self, message, status=400, **extra):
        super().__init__(message)
        self.message, self.status, self.extra = message, status, extra


def now_local() -> datetime:
    """Naive datetime in the hostel's timezone (all bookings are stored in local wall-clock time)."""
    try:
        tz = ZoneInfo(current_app.config.get("TIMEZONE", "Asia/Kolkata"))
    except Exception:
        tz = ZoneInfo("Asia/Kolkata")
    return datetime.now(tz).replace(tzinfo=None, microsecond=0)


def parse_date(v, field="date") -> date:
    try:
        return date.fromisoformat(str(v))
    except Exception:
        raise ApiError(f"Invalid {field}; expected YYYY-MM-DD")


def parse_time(v, field="time") -> time:
    try:
        h, m = str(v).split(":")[:2]
        return time(int(h), int(m))
    except Exception:
        raise ApiError(f"Invalid {field}; expected HH:MM")


def hhmm(t) -> str | None:
    return t.strftime("%H:%M") if t else None


def combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def add_minutes(d: date, t: time, minutes: int) -> datetime:
    return combine(d, t) + timedelta(minutes=minutes)


def iso(dt):
    return dt.isoformat() if dt else None


def _has_nul(v):
    if isinstance(v, str):
        return "\x00" in v
    if isinstance(v, dict):
        return any(_has_nul(k) or _has_nul(x) for k, x in v.items())
    if isinstance(v, list):
        return any(_has_nul(x) for x in v)
    return False


def json_body() -> dict:
    """The request body as a dict. Missing body -> {}; non-object JSON or NUL characters -> 400 (never a 500)."""
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object")
    if _has_nul(data):
        raise ApiError("Invalid characters in request")
    return data
