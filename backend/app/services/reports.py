import csv
import io
from collections import Counter, defaultdict
from datetime import date, timedelta

from app.models import Booking, Machine
from app.services import settings as S
from app.utils import common as tm


def _rows(start: date, end: date):
    return Booking.query.filter(Booking.booking_date >= start, Booking.booking_date <= end).all()


def build_report(start: date, end: date, label: str):
    bs = _rows(start, end)
    counts = Counter(b.status for b in bs)
    done = [b for b in bs if b.status == "COMPLETED"]
    # revenue = payments the operator verified and has not refunded (REJECTED/REFUNDED/PENDING never count)
    paid = [b for b in bs if b.payment_status == "VERIFIED"]
    revenue = sum(b.price_snapshot for b in paid)
    modes = Counter(b.wash_mode.name for b in bs if b.status not in ("EXPIRED", "REJECTED"))
    by_hour = Counter(b.start_time.hour for b in bs if b.status not in ("EXPIRED", "REJECTED", "CANCELLED"))
    by_day = defaultdict(lambda: {"bookings": 0, "revenue": 0.0})
    for b in bs:
        if b.status in ("EXPIRED", "REJECTED"):
            continue
        by_day[b.booking_date.isoformat()]["bookings"] += 1
        if b in paid:
            by_day[b.booking_date.isoformat()]["revenue"] += float(b.price_snapshot)
    # machine utilisation = washing minutes of completed jobs / (working machines * opening minutes * days)
    days = (end - start).days + 1
    open_min = (tm.combine(start, S.get_time("close_time")) - tm.combine(start, S.get_time("open_time"))).seconds // 60
    machines = Machine.query.filter(Machine.status.in_(("AVAILABLE", "OCCUPIED"))).count() or 1
    per_machine = Counter()
    for b in done:
        per_machine[b.machine.machine_number if b.machine else "Unassigned"] += b.duration_snapshot
    util = round(100 * sum(per_machine.values()) / (machines * open_min * days), 1) if open_min else 0
    return {
        "label": label, "start": start.isoformat(), "end": end.isoformat(),
        "total_bookings": sum(v for k, v in counts.items() if k not in ("EXPIRED", "REJECTED")),
        "status_counts": dict(counts), "completed": len(done), "cancelled": counts.get("CANCELLED", 0),
        "no_shows": counts.get("NO_SHOW", 0), "revenue": float(revenue),
        "popular_mode": modes.most_common(1)[0][0] if modes else None,
        "mode_counts": [{"name": k, "count": v} for k, v in modes.most_common()],
        "estimated_water_litres": int(sum(b.water_snapshot for b in done)),
        "machine_utilization_pct": util,
        "machine_minutes": [{"machine": k, "minutes": v} for k, v in sorted(per_machine.items())],
        "demand_by_hour": [{"hour": f"{h:02d}:00", "count": by_hour.get(h, 0)} for h in range(7, 22)],
        "by_day": [{"date": (start + timedelta(days=i)).isoformat(),
                    **by_day.get((start + timedelta(days=i)).isoformat(), {"bookings": 0, "revenue": 0.0})}
                   for i in range(days)],
        "note": "Water figures are estimates from the wash-mode configuration, not meter readings.",
    }


def _safe(v):
    """Neutralise spreadsheet formula injection (cells starting with = + - @ are prefixed with an apostrophe)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


class _SafeWriter:
    def __init__(self, w):
        self.w = w

    def writerow(self, row):
        self.w.writerow([_safe(c) for c in row])


def report_csv(rep):
    out = io.StringIO()
    w = _SafeWriter(csv.writer(out))
    w.writerow(["WashMate report", rep["label"], rep["start"], rep["end"]])
    for k in ("total_bookings", "completed", "cancelled", "no_shows", "revenue", "popular_mode",
              "estimated_water_litres", "machine_utilization_pct"):
        w.writerow([k, rep[k]])
    w.writerow([])
    w.writerow(["date", "bookings", "verified_revenue"])
    for d in rep["by_day"]:
        w.writerow([d["date"], d["bookings"], d["revenue"]])
    w.writerow([])
    w.writerow(["hour", "bookings"])
    for h in rep["demand_by_hour"]:
        w.writerow([h["hour"], h["count"]])
    w.writerow([])
    w.writerow(["wash_mode", "bookings"])
    for m in rep["mode_counts"]:
        w.writerow([m["name"], m["count"]])
    return "\ufeff" + out.getvalue()  # BOM so Excel opens UTF-8 correctly


def overview(today: date):
    bs = Booking.query.filter(Booking.booking_date == today).all()
    c = Counter(b.status for b in bs)
    ms = Counter(m.status for m in Machine.query.all())
    now = tm.now_local()
    upcoming = sorted([b for b in bs if b.status in ("CONFIRMED", "ARRIVED") and tm.combine(b.booking_date, b.start_time) >= now - timedelta(minutes=30)],
                      key=lambda b: b.start_time)
    from app.models import Payment
    pending = Payment.query.filter_by(status="PENDING").join(Booking).filter(Booking.status == "PAYMENT_SUBMITTED").count()
    return {
        "date": today.isoformat(),
        "total_today": sum(v for k, v in c.items() if k not in ("EXPIRED", "REJECTED")),
        "confirmed": c.get("CONFIRMED", 0) + c.get("ARRIVED", 0), "pending_verification": pending,
        "washing": c.get("WASHING", 0), "completed": c.get("COMPLETED", 0), "no_shows": c.get("NO_SHOW", 0),
        "machines": {"available": ms.get("AVAILABLE", 0), "occupied": ms.get("OCCUPIED", 0),
                     "maintenance": ms.get("MAINTENANCE", 0), "inactive": ms.get("INACTIVE", 0)},
        "revenue_today": float(sum(b.price_snapshot for b in bs if b.payment_status == "VERIFIED")),
        "upcoming_ids": [b.id for b in upcoming[:8]],
    }
