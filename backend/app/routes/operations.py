"""Bookings, payments, rescheduling, notifications, reports, cron."""
import hmac
from datetime import timedelta

from flask import Blueprint, Response, current_app, jsonify, request

from app.extensions import db
from app.models import Booking, Notification, Payment, RescheduleRequest
from app.services import bookings as svc
from app.services import reports as rep
from app.services import scheduling as sch
from app.services.notifications import process_due_reminders
from app.services.serializers import booking_dict, payment_dict, reschedule_dict
from app.utils import common as tm
from app.utils.auth import login_required, operator_required, student_required
from app.utils.common import ApiError, parse_date, parse_time

bp = Blueprint("ops", __name__, url_prefix="/api")


def _body():
    return request.get_json(silent=True) or {}


def _own_or_operator(user, bid) -> Booking:
    b = db.session.get(Booking, bid)
    if not b or (user.role != "OPERATOR" and b.student_id != user.id):
        raise ApiError("Booking not found", 404)  # 404 so other students' bookings are not revealed
    return b


def _get(bid) -> Booking:
    b = db.session.get(Booking, bid)
    if not b:
        raise ApiError("Booking not found", 404)
    return b


# ---- bookings -------------------------------------------------------------------------
@bp.post("/bookings")
@student_required
def create_booking(user):
    d = _body()
    try:
        mode_id = int(d.get("wash_mode_id"))
    except (TypeError, ValueError):
        raise ApiError("wash_mode_id is required")
    b = svc.create_booking(user, mode_id, parse_date(d.get("booking_date"), "booking_date"),
                           parse_time(d.get("start_time"), "start_time"))
    return jsonify({"booking": booking_dict(b)}), 201


@bp.get("/bookings/my")
@student_required
def my_bookings(user):
    sch.expire_reservations()
    rows = (Booking.query.filter_by(student_id=user.id)
            .order_by(Booking.booking_date.desc(), Booking.start_time.desc()).all())
    return jsonify({"bookings": [booking_dict(b) for b in rows]})


@bp.get("/bookings")
@operator_required
def all_bookings(user):
    sch.expire_reservations()
    q = Booking.query
    if request.args.get("date"):
        q = q.filter(Booking.booking_date == parse_date(request.args["date"]))
    if request.args.get("from"):
        q = q.filter(Booking.booking_date >= parse_date(request.args["from"]))
    if request.args.get("to"):
        q = q.filter(Booking.booking_date <= parse_date(request.args["to"]))
    if request.args.get("status"):
        q = q.filter(Booking.status.in_(request.args["status"].upper().split(",")))
    q = q.order_by(Booking.booking_date.desc(), Booking.start_time.desc()).limit(500)
    return jsonify({"bookings": [booking_dict(b, True) for b in q.all()]})


@bp.get("/bookings/at-risk")
@operator_required
def at_risk(user):
    return jsonify({"bookings": [booking_dict(b, True) for b in sch.at_risk_bookings()],
                    "working_machines": sch.working_machine_count()})


@bp.get("/bookings/<int:bid>")
@login_required
def get_booking(user, bid):
    b = _own_or_operator(user, bid)
    d = booking_dict(b, user.role == "OPERATOR")
    d["reschedules"] = [reschedule_dict(r) for r in RescheduleRequest.query.filter_by(booking_id=b.id).order_by(RescheduleRequest.id)]
    return jsonify({"booking": d})


def _op_action(fn):
    def view(user, bid, **kw):
        return jsonify({"booking": booking_dict(fn(user, _get(bid)), True)})
    return view


@bp.patch("/bookings/<int:bid>/arrival")
@operator_required
def arrival(user, bid):
    return jsonify({"booking": booking_dict(svc.mark_arrived(user, _get(bid)), True)})


@bp.patch("/bookings/<int:bid>/assign")
@operator_required
def assign(user, bid):
    return jsonify({"booking": booking_dict(svc.assign(user, _get(bid), _body().get("machine_id")), True)})


@bp.patch("/bookings/<int:bid>/start")
@operator_required
def start(user, bid):
    return jsonify({"booking": booking_dict(svc.start_wash(user, _get(bid), _body().get("machine_id")), True)})


@bp.patch("/bookings/<int:bid>/complete")
@operator_required
def complete(user, bid):
    return jsonify({"booking": booking_dict(svc.complete_wash(user, _get(bid)), True)})


@bp.patch("/bookings/<int:bid>/no-show")
@operator_required
def no_show(user, bid):
    return jsonify({"booking": booking_dict(svc.mark_no_show(user, _get(bid)), True)})


@bp.post("/bookings/<int:bid>/propose-reschedule")
@operator_required
def propose(user, bid):
    svc.propose_reschedule(user, _get(bid), str(_body().get("message", ""))[:300])
    return jsonify({"message": "Student notified"})


@bp.patch("/bookings/<int:bid>/cancel")
@login_required
def cancel(user, bid):
    d = _body()
    b = svc.cancel_booking(user, _own_or_operator(user, bid), str(d.get("reason", "")).strip(), bool(d.get("refund")))
    return jsonify({"booking": booking_dict(b, user.role == "OPERATOR")})


# ---- payments -------------------------------------------------------------------------
@bp.post("/payments/submit")
@student_required
def pay_submit(user):
    d = _body()
    try:
        bid = int(d.get("booking_id"))
    except (TypeError, ValueError):
        raise ApiError("booking_id is required")
    return jsonify({"booking": booking_dict(svc.submit_payment(user, bid, d.get("transaction_reference")))})


@bp.get("/payments/pending")
@operator_required
def pay_pending(user):
    rows = (Payment.query.join(Booking).filter(Payment.status == "PENDING", Booking.status == "PAYMENT_SUBMITTED")
            .order_by(Payment.paid_at).all())
    return jsonify({"payments": [payment_dict(p) for p in rows]})


@bp.get("/payments")
@operator_required
def pay_all(user):
    q = Payment.query.filter(Payment.transaction_reference.isnot(None))
    if request.args.get("status"):
        q = q.filter(Payment.status == request.args["status"].upper())
    return jsonify({"payments": [payment_dict(p) for p in q.order_by(Payment.id.desc()).limit(500)]})


@bp.patch("/payments/<int:pid>/verify")
@operator_required
def pay_verify(user, pid):
    return jsonify({"booking": booking_dict(svc.verify_payment(user, pid), True)})


@bp.patch("/payments/<int:pid>/reject")
@operator_required
def pay_reject(user, pid):
    return jsonify({"booking": booking_dict(svc.reject_payment(user, pid, str(_body().get("reason", ""))), True)})


@bp.patch("/payments/<int:pid>/refund")
@operator_required
def pay_refund(user, pid):
    return jsonify({"booking": booking_dict(svc.mark_refunded(user, pid), True)})


# ---- rescheduling ---------------------------------------------------------------------
@bp.post("/reschedule")
@student_required
def resched_create(user):
    d = _body()
    b = db.session.get(Booking, int(d.get("booking_id") or 0))
    if not b or b.student_id != user.id:
        raise ApiError("Booking not found", 404)
    r = svc.request_reschedule(user, b, parse_date(d.get("requested_date"), "requested_date"),
                               parse_time(d.get("requested_start_time"), "requested_start_time"), d.get("reason"))
    return jsonify({"request": reschedule_dict(r)}), 201


@bp.get("/reschedule")
@login_required
def resched_list(user):
    q = RescheduleRequest.query.join(Booking)
    if user.role != "OPERATOR":
        q = q.filter(Booking.student_id == user.id)
    if request.args.get("status"):
        q = q.filter(RescheduleRequest.status == request.args["status"].upper())
    return jsonify({"requests": [reschedule_dict(r, user.role == "OPERATOR")
                                 for r in q.order_by(RescheduleRequest.id.desc()).limit(300)]})


@bp.patch("/reschedule/<int:rid>")
@operator_required
def resched_review(user, rid):
    r = db.session.get(RescheduleRequest, rid)
    if not r:
        raise ApiError("Request not found", 404)
    d = _body()
    svc.review_reschedule(user, r, str(d.get("action", "")).lower(), d.get("note"))
    return jsonify({"request": reschedule_dict(r, True)})


# ---- notifications --------------------------------------------------------------------
@bp.get("/notifications")
@login_required
def notifications(user):
    sch.expire_reservations()
    process_due_reminders()  # lazy fallback so reminders work even without an external cron
    rows = Notification.query.filter_by(user_id=user.id).order_by(Notification.id.desc()).limit(100).all()
    return jsonify({"notifications": [n.to_dict() for n in rows],
                    "unread": sum(1 for n in rows if not n.is_read)})


@bp.patch("/notifications/<int:nid>/read")
@login_required
def notif_read(user, nid):
    n = db.session.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise ApiError("Notification not found", 404)
    n.is_read = True
    db.session.commit()
    return jsonify({"notification": n.to_dict()})


@bp.patch("/notifications/read-all")
@login_required
def notif_read_all(user):
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "ok"})


# ---- reports --------------------------------------------------------------------------
def _csv_or_json(r):
    if request.args.get("format") == "csv":
        return Response(rep.report_csv(r), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=washmate-{r['label']}-{r['start']}.csv"})
    return jsonify({"report": r})


@bp.get("/reports/overview")
@operator_required
def overview(user):
    sch.expire_reservations()
    d = rep.overview(tm.now_local().date())
    ups = Booking.query.filter(Booking.id.in_(d.pop("upcoming_ids") or [0])).order_by(Booking.start_time).all()
    d["upcoming"] = [booking_dict(b, True) for b in ups]
    d["at_risk_count"] = len(sch.at_risk_bookings())
    return jsonify({"overview": d})


@bp.get("/reports/daily")
@operator_required
def daily(user):
    d = parse_date(request.args.get("date") or tm.now_local().date().isoformat())
    return _csv_or_json(rep.build_report(d, d, "daily"))


@bp.get("/reports/weekly")
@operator_required
def weekly(user):
    end = parse_date(request.args.get("end") or tm.now_local().date().isoformat(), "end")
    return _csv_or_json(rep.build_report(end - timedelta(days=6), end, "weekly"))


@bp.get("/reports/monthly")
@operator_required
def monthly(user):
    m = request.args.get("month") or tm.now_local().strftime("%Y-%m")
    first = parse_date(m + "-01", "month")
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return _csv_or_json(rep.build_report(first, nxt - timedelta(days=1), "monthly"))


# ---- cron (Vercel Cron / external scheduler) ------------------------------------------
@bp.route("/cron/reminders", methods=["GET", "POST"])
def cron_reminders():
    secret = current_app.config.get("CRON_SECRET")
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not secret or not hmac.compare_digest(token, secret):
        raise ApiError("Unauthorized", 401)
    expired = sch.expire_reservations()
    return jsonify({"reminders_sent": process_due_reminders(), "reservations_expired": expired})


@bp.get("/health")
def health():
    db.session.execute(db.text("SELECT 1"))
    return jsonify({"status": "ok", "time": tm.now_local().isoformat()})
