"""Capacity engine for fixed appointments.

A booking occupies one machine for [start, start + duration + turnaround buffer).
A new booking fits iff, at every instant of its own interval, the number of overlapping active
bookings is lower than the number of working machines (AVAILABLE or OCCUPIED).
"""
import threading
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import text

from app.extensions import db
from app.models import ACTIVE_BOOKING, WORKING_MACHINE, Booking, Machine, MachineAssignment
from app.services import settings as S
from app.utils import common as tm
from app.utils.common import ApiError

_sqlite_lock = threading.RLock()


@contextmanager
def booking_lock():
    """Serialises every capacity-changing transaction (PostgreSQL advisory lock / SQLite process lock).
    Callers must commit INSIDE the with-block so the lock covers check + write."""
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(424242)"))
        yield
    else:
        with _sqlite_lock:
            yield


def working_machine_count():
    return Machine.query.filter(Machine.status.in_(WORKING_MACHINE)).count()


def occupancy(b: Booking):
    start = tm.combine(b.booking_date, b.start_time)
    end = tm.combine(b.booking_date, b.end_time) + timedelta(minutes=S.get_int("turnaround_buffer_minutes"))
    return start, end


def expire_reservations():
    """Release capacity held by unpaid reservations whose hold window has passed.
    Each row is flipped with a conditional UPDATE so concurrent callers notify exactly once."""
    from app.services.notifications import notify
    now = tm.now_local()
    rows = Booking.query.filter(Booking.status == "RESERVED", Booking.expires_at.isnot(None),
                                Booking.expires_at <= now).all()
    done = 0
    for b in rows:
        changed = (Booking.query.filter(Booking.id == b.id, Booking.status == "RESERVED")
                   .update({"status": "EXPIRED"}, synchronize_session=False))
        if changed:
            done += 1
            notify(b.student_id, "Reservation expired",
                   "Your unpaid reservation expired and the slot was released.", "EXPIRED", b.id)
    if rows:
        db.session.commit()
    return done


def _active_on(date_, exclude_id=None):
    """Active bookings that can occupy a machine on `date_`: that day's, plus the previous day's
    (a late wash + turnaround buffer can run past midnight)."""
    q = Booking.query.filter(Booking.booking_date.in_([date_ - timedelta(days=1), date_]),
                             Booking.status.in_(ACTIVE_BOOKING))
    if exclude_id:
        q = q.filter(Booking.id != exclude_id)
    now = tm.now_local()
    return [b for b in q.all() if not (b.status == "RESERVED" and b.expires_at and b.expires_at <= now)]


def remaining_capacity(date_, start_dt, end_dt, exclude_id=None, bookings=None, working=None):
    """Free machines throughout [start_dt, end_dt) (min over time)."""
    working = working_machine_count() if working is None else working
    ivs = [occupancy(b) for b in (bookings if bookings is not None else _active_on(date_, exclude_id))]
    points = [start_dt] + [s for s, _ in ivs if start_dt < s < end_dt]
    peak = max(sum(1 for s, e in ivs if s <= p < e) for p in points)
    return working - peak


def ensure_capacity(date_, start_time, duration, exclude_id=None):
    start = tm.combine(date_, start_time)
    end = start + timedelta(minutes=duration + S.get_int("turnaround_buffer_minutes"))
    if remaining_capacity(date_, start, end, exclude_id) <= 0:
        raise ApiError("That time is fully booked. Please choose another slot.", 409)


def validate_slot(date_, start_time, duration):
    """Business-hour / advance-window / past-time validation."""
    now = tm.now_local()
    start = tm.combine(date_, start_time)
    end = start + timedelta(minutes=duration)
    if start < now:
        raise ApiError("Appointments cannot be in the past")
    if date_ > now.date() + timedelta(days=S.get_int("max_advance_days")):
        raise ApiError(f"Bookings open only {S.get_int('max_advance_days')} days ahead")
    if start_time < S.get_time("open_time") or end > tm.combine(date_, S.get_time("close_time")):
        raise ApiError("The wash must finish within operating hours "
                       f"({S.get_str('open_time')}–{S.get_str('close_time')})")
    interval = S.get_int("slot_interval_minutes")
    open_dt = tm.combine(date_, S.get_time("open_time"))
    if int((start - open_dt).total_seconds() // 60) % interval:
        raise ApiError("Start time does not align with the slot grid")


def slots_for(date_, duration, exclude_id=None):
    """All grid slots for a day with remaining capacity."""
    now = tm.now_local()
    working = working_machine_count()
    bookings = _active_on(date_, exclude_id)
    buf = S.get_int("turnaround_buffer_minutes")
    cur = tm.combine(date_, S.get_time("open_time"))
    close = tm.combine(date_, S.get_time("close_time"))
    step = timedelta(minutes=S.get_int("slot_interval_minutes"))
    out = []
    while cur + timedelta(minutes=duration) <= close:
        if cur >= now:
            rem = remaining_capacity(date_, cur, cur + timedelta(minutes=duration + buf),
                                     bookings=bookings, working=working)
            out.append({"start_time": cur.strftime("%H:%M"),
                        "end_time": (cur + timedelta(minutes=duration)).strftime("%H:%M"),
                        "remaining": max(rem, 0), "available": rem > 0})
        cur += step
    return {"date": date_.isoformat(), "working_machines": working, "slots": out}


def at_risk_bookings():
    """Future active bookings that no longer fit the working-machine count (never auto-cancelled)."""
    today = tm.now_local().date()
    working = working_machine_count()
    dates = {d for (d,) in db.session.query(Booking.booking_date).filter(
        Booking.booking_date >= today, Booking.status.in_(ACTIVE_BOOKING)).distinct()}
    risky = []
    for d in sorted(dates):
        admitted = []
        # earliest committed bookings keep priority; later ones are flagged
        for b in sorted(_active_on(d), key=lambda x: (x.confirmed_at or x.created_at, x.id)):
            s, e = occupancy(b)
            points = [s] + [a for a, _ in (occupancy(x) for x in admitted) if s < a < e]
            ivs = [occupancy(x) for x in admitted]
            peak = max(sum(1 for a, z in ivs if a <= p < z) for p in points)
            if peak >= working:
                if b.booking_date == d:  # previous-day bookings are judged on their own date
                    risky.append(b)
            else:
                admitted.append(b)
    return risky


def machine_conflict(machine_id, booking: Booking):
    s, e = occupancy(booking)
    others = Booking.query.filter(Booking.machine_id == machine_id, Booking.id != booking.id,
                                  Booking.booking_date == booking.booking_date,
                                  Booking.status.in_(("CONFIRMED", "ARRIVED", "WASHING"))).all()
    for o in others:
        os_, oe = occupancy(o)
        if os_ < e and s < oe:
            return o
    return None


def assign_machine(booking: Booking, machine_id: int):
    m = db.session.get(Machine, machine_id)
    if not m:
        raise ApiError("Machine not found", 404)
    if m.status not in WORKING_MACHINE:
        raise ApiError(f"Machine {m.machine_number} is {m.status.lower()} and cannot be assigned", 409)
    clash = machine_conflict(m.id, booking)
    if clash:
        raise ApiError(f"Machine {m.machine_number} is already assigned during an overlapping appointment", 409)
    booking.machine_id = m.id
    MachineAssignment.query.filter_by(booking_id=booking.id, started_at=None).delete()
    db.session.add(MachineAssignment(booking_id=booking.id, machine_id=m.id, assigned_at=tm.now_local()))
    return m
