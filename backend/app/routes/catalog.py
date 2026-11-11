"""Machines, wash modes, settings."""
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import MACHINE_STATUSES, ACTIVE_BOOKING, Booking, Machine, WashMode
from app.services import scheduling as sch
from app.services import settings as S
from app.services.notifications import notify_operators
from app.utils import common as tm
from app.utils.auth import audit, login_required, operator_required
from app.utils.common import ApiError, parse_date

bp = Blueprint("catalog", __name__, url_prefix="/api")


def _num(d, key, typ=int, minimum=0, required=True):
    if key not in d:
        if required:
            raise ApiError(f"{key} is required")
        return None
    try:
        v = typ(d[key])
    except (TypeError, ValueError):
        raise ApiError(f"{key} must be a number")
    if v < minimum:
        raise ApiError(f"{key} must be at least {minimum}")
    return v


# ---- machines -------------------------------------------------------------------------
def _machine_view(m):
    d = m.to_dict()
    cur = Booking.query.filter(Booking.machine_id == m.id, Booking.status == "WASHING").first()
    d["current_booking"] = None
    if cur:
        d["current_booking"] = {"id": cur.id, "ref": cur.booking_reference, "student": cur.student.name,
                                "mode": cur.wash_mode.name, "ends": tm.hhmm(cur.end_time)}
    today = tm.now_local().date()
    d["assignments_today"] = Booking.query.filter(Booking.machine_id == m.id, Booking.booking_date == today,
                                                  Booking.status.in_(ACTIVE_BOOKING)).count()
    return d


@bp.get("/machines")
@operator_required
def list_machines(user):
    ms = Machine.query.order_by(Machine.machine_number).all()
    return jsonify({"machines": [_machine_view(m) for m in ms], "working": sch.working_machine_count()})


@bp.post("/machines")
@operator_required
def add_machine(user):
    d = request.get_json(silent=True) or {}
    num = str(d.get("machine_number", "")).strip()
    if not num or len(num) > 20:
        raise ApiError("Machine number is required (max 20 characters)")
    if Machine.query.filter_by(machine_number=num).first():
        raise ApiError("A machine with this number already exists", 409)
    m = Machine(machine_number=num, status="AVAILABLE")
    db.session.add(m)
    db.session.flush()
    audit(user, "MACHINE_ADDED", "machine", m.id, num)
    db.session.commit()
    return jsonify({"machine": _machine_view(m)}), 201


@bp.patch("/machines/<int:mid>")
@operator_required
def edit_machine(user, mid):
    m = db.session.get(Machine, mid)
    if not m:
        raise ApiError("Machine not found", 404)
    d = request.get_json(silent=True) or {}
    old = m.status
    if "machine_number" in d:
        num = str(d["machine_number"]).strip()
        if not num or Machine.query.filter(Machine.machine_number == num, Machine.id != m.id).first():
            raise ApiError("Invalid or duplicate machine number", 409)
        m.machine_number = num
    if "maintenance_note" in d:
        m.maintenance_note = str(d["maintenance_note"] or "")[:300]
    if "status" in d:
        st = str(d["status"]).upper()
        if st not in MACHINE_STATUSES:
            raise ApiError("Invalid status")
        if st in ("MAINTENANCE", "INACTIVE") and Booking.query.filter_by(machine_id=m.id, status="WASHING").first():
            raise ApiError("A wash is running on this machine. Complete it first.", 409)
        m.status = st
        m.maintenance_since = tm.now_local() if st in ("MAINTENANCE", "INACTIVE") and old not in ("MAINTENANCE", "INACTIVE") else (
            m.maintenance_since if st in ("MAINTENANCE", "INACTIVE") else None)
        if st == "AVAILABLE":
            m.maintenance_note = None if "maintenance_note" not in d else m.maintenance_note
    audit(user, "MACHINE_UPDATED", "machine", m.id, f"{old}->{m.status}")
    db.session.commit()
    at_risk = []
    if m.status != old:
        risky = sch.at_risk_bookings()
        if m.status in ("MAINTENANCE", "INACTIVE") and risky:
            notify_operators("Capacity reduced", f"Machine {m.machine_number} is {m.status.lower()}: "
                             f"{len(risky)} confirmed/pending booking(s) may be affected.", "CAPACITY_ALERT")
            db.session.commit()
        at_risk = [b.id for b in risky]
    return jsonify({"machine": _machine_view(m), "at_risk_booking_ids": at_risk, "working": sch.working_machine_count()})


@bp.get("/machines/availability")
@login_required
def availability(user):
    sch.expire_reservations()
    d = parse_date(request.args.get("date"), "date")
    mode = db.session.get(WashMode, request.args.get("wash_mode_id", type=int) or 0)
    if not mode:
        raise ApiError("wash_mode_id is required", 400)
    return jsonify(sch.slots_for(d, mode.duration_minutes))


# ---- wash modes -----------------------------------------------------------------------
@bp.get("/wash-modes")
@login_required
def list_modes(user):
    q = WashMode.query.order_by(WashMode.id)
    if user.role != "OPERATOR" or not request.args.get("all"):
        q = q.filter_by(is_active=True)
    return jsonify({"wash_modes": [m.to_dict() for m in q.all()]})


def _mode_fields(d, m, partial):
    if "name" in d or not partial:
        name = str(d.get("name", "")).strip()
        if not name or len(name) > 60:
            raise ApiError("Name is required (max 60 characters)")
        dup = WashMode.query.filter(WashMode.name == name, WashMode.id != (m.id or 0)).first()
        if dup:
            raise ApiError("A wash mode with this name already exists", 409)
        m.name = name
    if "description" in d:
        m.description = str(d["description"] or "")[:400]
    if "duration_minutes" in d or not partial:
        m.duration_minutes = _num(d, "duration_minutes", int, 5)
    if "water_litres" in d or not partial:
        m.water_litres = _num(d, "water_litres", int, 0)
    if "price" in d or not partial:
        m.price = _num(d, "price", float, 0)
    if "is_active" in d:
        m.is_active = bool(d["is_active"])


@bp.post("/wash-modes")
@operator_required
def create_mode(user):
    m = WashMode()
    _mode_fields(request.get_json(silent=True) or {}, m, False)
    db.session.add(m)
    db.session.flush()
    audit(user, "MODE_CREATED", "wash_mode", m.id, m.name)
    db.session.commit()
    return jsonify({"wash_mode": m.to_dict()}), 201


@bp.patch("/wash-modes/<int:mid>")
@operator_required
def edit_mode(user, mid):
    m = db.session.get(WashMode, mid)
    if not m:
        raise ApiError("Wash mode not found", 404)
    _mode_fields(request.get_json(silent=True) or {}, m, True)  # bookings keep their own snapshots
    audit(user, "MODE_UPDATED", "wash_mode", m.id, m.name)
    db.session.commit()
    return jsonify({"wash_mode": m.to_dict()})


@bp.delete("/wash-modes/<int:mid>")
@operator_required
def delete_mode(user, mid):
    m = db.session.get(WashMode, mid)
    if not m:
        raise ApiError("Wash mode not found", 404)
    if Booking.query.filter_by(wash_mode_id=m.id).first():  # safe deletion: keep history, just deactivate
        m.is_active = False
        audit(user, "MODE_DEACTIVATED", "wash_mode", m.id)
        db.session.commit()
        return jsonify({"wash_mode": m.to_dict(), "deactivated": True})
    audit(user, "MODE_DELETED", "wash_mode", m.id, m.name)
    db.session.delete(m)
    db.session.commit()
    return jsonify({"deleted": True})


# ---- settings -------------------------------------------------------------------------
@bp.get("/settings")
@login_required
def get_settings(user):
    s = S.all_settings()
    return jsonify({"settings": {k: s[k] for k in (S.PUBLIC_KEYS if user.role != "OPERATOR" else s)}})


@bp.patch("/settings")
@operator_required
def patch_settings(user):
    S.update_settings(request.get_json(silent=True) or {})
    audit(user, "SETTINGS_UPDATED", "settings", None, ",".join((request.get_json(silent=True) or {}).keys()))
    db.session.commit()
    return jsonify({"settings": S.all_settings()})
