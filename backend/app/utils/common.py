"""Time helpers and shared error type. Always call `now_local()` via this module (tests patch it)."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app


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
