"""Booking lifecycle: create, pay, verify, arrive, wash, cancel, reschedule."""
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (ACTIVE_BOOKING, Booking, Machine, MachineAssignment, Payment, RescheduleRequest,
                        WashMode)
from app.services import scheduling as sch
from app.services import settings as S
from app.services.notifications import notify, notify_operators
from app.utils import common as tm
from app.utils.auth import audit
from app.utils.common import ApiError


def ref_of(b):
    return b.booking_reference or f"REQ-{b.id}"


def _next_reference(year):
    prefix = f"WM-{year}-"
    nums = [int(r.split("-")[-1]) for (r,) in db.session.query(Booking.booking_reference)
            .filter(Booking.booking_reference.like(prefix + "%")).all()]
    return f"{prefix}{(max(nums) + 1 if nums else 1):03d}"


def create_booking(student, wash_mode_id, date_, start_time):
    mode = db.session.get(WashMode, wash_mode_id)
    if not mode or not mode.is_active:
        raise ApiError("Washing mode not available", 404)
    sch.validate_slot(date_, start_time, mode.duration_minutes)
    with sch.booking_lock():
        sch.expire_reservations()
        sch.ensure_capacity(date_, start_time, mode.duration_minutes)
        start = tm.combine(date_, start_time)
        end = start + timedelta(minutes=mode.duration_minutes)
        for o in Booking.query.filter(Booking.student_id == student.id, Booking.booking_date == date_,
                                      Booking.status.in_(ACTIVE_BOOKING)).all():
            s2, e2 = sch.occupancy(o)
            if s2 < end and start < e2:
                raise ApiError("You already have an appointment overlapping this time", 409)
        now = tm.now_local()
        b = Booking(student_id=student.id, wash_mode_id=mode.id, booking_date=date_, start_time=start_time,
                    end_time=end.time(), duration_snapshot=mode.duration_minutes, price_snapshot=mode.price,
                    water_snapshot=mode.water_litres, status="RESERVED", payment_status="PENDING",
                    expires_at=now + timedelta(minutes=S.get_int("reservation_hold_minutes")))
        db.session.add(b)
        db.session.flush()
        db.session.add(Payment(booking_id=b.id, amount=b.price_snapshot, payment_method="UPI", status="PENDING"))
        audit(student, "BOOKING_CREATED", "booking", b.id, f"{date_} {start_time}")
        db.session.commit()
    return b


def submit_payment(student, booking_id, txn_ref):
    ref = (txn_ref or "").strip().upper()
    if len(ref) < 6 or len(ref) > 40 or not ref.replace("-", "").isalnum():
        raise ApiError("Enter the UPI transaction reference (6-40 letters/digits)")
    sch.expire_reservations()
    b = db.session.get(Booking, booking_id)
    if not b or b.student_id != student.id:
        raise ApiError("Booking not found", 404)
    if b.status == "EXPIRED":
        raise ApiError("This reservation expired. Please book again.", 410)
    if b.status != "RESERVED" or b.payment.status != "PENDING" or b.payment.transaction_reference:
        raise ApiError("Payment cannot be submitted for this booking", 409)
    if Payment.query.filter_by(transaction_reference=ref).first():
        raise ApiError("This transaction reference has already been used", 409)
    p = b.payment
    p.transaction_reference, p.paid_at = ref, tm.now_local()
    b.status, b.expires_at = "PAYMENT_SUBMITTED", None
    audit(student, "PAYMENT_SUBMITTED", "payment", p.id, ref)
    notify_operators("Payment awaiting verification",
                     f"{student.name} submitted ref {ref} for ₹{b.price_snapshot:g}.", "PAYMENT_PENDING", b.id)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("This transaction reference has already been used", 409)
    return b


def verify_payment(op, payment_id):
    with sch.booking_lock():
        p = db.session.get(Payment, payment_id)
        if not p:
            raise ApiError("Payment not found", 404)
        b = p.booking
        if p.status != "VERIFIED" and (p.status != "PENDING" or b.status != "PAYMENT_SUBMITTED"):
            raise ApiError("Only submitted payments can be verified", 409)
        if p.status == "VERIFIED":
            return b
        now = tm.now_local()
        p.status, p.verified_by, p.verified_at = "VERIFIED", op.id, now
        b.payment_status, b.status, b.confirmed_at = "VERIFIED", "CONFIRMED", now
        b.booking_reference = _next_reference(b.booking_date.year)  # serialised by booking_lock
        audit(op, "PAYMENT_VERIFIED", "payment", p.id, ref_of(b))
        notify(b.student_id, "Payment verified – booking confirmed",
               f"{ref_of(b)} on {b.booking_date} at {tm.hhmm(b.start_time)} is confirmed.", "BOOKING_CONFIRMED", b.id)
        db.session.commit()
    return b


def reject_payment(op, payment_id, reason):
    p = db.session.get(Payment, payment_id)
    if not p:
        raise ApiError("Payment not found", 404)
    b = p.booking
    if p.status != "PENDING" or b.status != "PAYMENT_SUBMITTED":
        raise ApiError("Only submitted payments can be rejected", 409)
    p.status, p.verified_by, p.verified_at, p.reject_reason = "REJECTED", op.id, tm.now_local(), (reason or "")[:300]
    b.payment_status, b.status = "REJECTED", "REJECTED"
    audit(op, "PAYMENT_REJECTED", "payment", p.id, reason)
    notify(b.student_id, "Payment rejected",
           f"We could not match your transaction. {reason or ''} The slot was released.".strip(), "PAYMENT_REJECTED", b.id)
    db.session.commit()
    return b


def mark_refunded(op, payment_id):
    p = db.session.get(Payment, payment_id)
    if not p or p.status != "VERIFIED" or p.booking.status not in ("CANCELLED", "NO_SHOW"):
        raise ApiError("Only verified payments of cancelled bookings can be marked refunded", 409)
    p.status = p.booking.payment_status = "REFUNDED"
    audit(op, "PAYMENT_REFUNDED", "payment", p.id, "refund processed manually by operator")
    notify(p.booking.student_id, "Refund processed", "The operator marked your payment as refunded.", "REFUND", p.booking.id)
    db.session.commit()
    return p.booking


def cancel_booking(user, b: Booking, reason, refund=False):
    if b.status not in ("RESERVED", "PAYMENT_SUBMITTED", "CONFIRMED", "ARRIVED", "WASHING"):
        raise ApiError("This booking can no longer be cancelled", 409)
    is_op = user.role == "OPERATOR"
    if not is_op:
        if b.status in ("ARRIVED", "WASHING"):
            raise ApiError("Please ask the operator to cancel a wash that has started", 403)
        cutoff = tm.combine(b.booking_date, b.start_time) - timedelta(minutes=S.get_int("student_cancel_cutoff_minutes"))
        if b.status == "CONFIRMED" and tm.now_local() > cutoff:
            raise ApiError(f"Cancellation closes {S.get_int('student_cancel_cutoff_minutes')} minutes before the appointment", 409)
    elif not (reason or "").strip():
        raise ApiError("A cancellation reason is required")
    was_washing, mid = b.status == "WASHING", b.machine_id
    b.status, b.cancel_reason, b.cancelled_by = "CANCELLED", (reason or "Cancelled by student")[:300], user.id
    if b.payment and b.payment.status == "PENDING":
        b.payment.status = b.payment_status = "REJECTED"
        b.payment.reject_reason = "Booking cancelled"
    elif b.payment and b.payment.status == "VERIFIED" and refund and is_op:
        b.payment.status = b.payment_status = "REFUNDED"
    if was_washing:
        _free_machine(mid, b.id)
    audit(user, "BOOKING_CANCELLED", "booking", b.id, b.cancel_reason)
    if is_op:
        notify(b.student_id, "Booking cancelled", f"{ref_of(b)} was cancelled by the operator: {b.cancel_reason}",
               "CANCELLED", b.id)
    else:
        notify_operators("Booking cancelled by student", f"{ref_of(b)} cancelled.", "CANCELLED", b.id)
        notify(b.student_id, "Booking cancelled", f"{ref_of(b)} was cancelled." + (
            " Contact the operator about your refund." if b.payment_status == "VERIFIED" else ""), "CANCELLED", b.id)
    db.session.commit()
    return b


def _free_machine(machine_id, booking_id):
    if not machine_id:
        return
    m = db.session.get(Machine, machine_id)
    others = Booking.query.filter(Booking.machine_id == machine_id, Booking.status == "WASHING",
                                  Booking.id != booking_id).count()
    if m and m.status == "OCCUPIED" and not others:
        m.status = "AVAILABLE"


def mark_arrived(op, b):
    if b.status != "CONFIRMED":
        raise ApiError("Only confirmed appointments can be marked as arrived", 409)
    b.status, b.arrival_time = "ARRIVED", tm.now_local()
    audit(op, "ARRIVED", "booking", b.id)
    db.session.commit()
    return b


def assign(op, b, machine_id):
    if b.status not in ("CONFIRMED", "ARRIVED"):
        raise ApiError("Machine can be assigned only to confirmed/arrived bookings", 409)
    with sch.booking_lock():
        m = sch.assign_machine(b, machine_id)
        audit(op, "MACHINE_ASSIGNED", "booking", b.id, m.machine_number)
        db.session.commit()
    return b


def start_wash(op, b, machine_id=None):
    if b.status != "ARRIVED":
        raise ApiError("Mark the student as arrived before starting the wash", 409)
    with sch.booking_lock():
        mid = machine_id or b.machine_id
        if not mid:
            raise ApiError("Assign a machine before starting", 400)
        m = db.session.get(Machine, mid)
        if m is None or m.status != "AVAILABLE":
            raise ApiError("Selected machine is not available right now", 409)
        if b.machine_id != m.id or not MachineAssignment.query.filter_by(booking_id=b.id, machine_id=m.id).first():
            sch.assign_machine(b, m.id)
        a = MachineAssignment.query.filter_by(booking_id=b.id, machine_id=m.id, completed_at=None).first()
        a.started_at = tm.now_local()
        m.status, b.status = "OCCUPIED", "WASHING"
        audit(op, "WASH_STARTED", "booking", b.id, m.machine_number)
        db.session.commit()
    return b


def complete_wash(op, b):
    if b.status != "WASHING":
        raise ApiError("Only a running wash can be completed", 409)
    now = tm.now_local()
    b.status, b.completed_at = "COMPLETED", now
    for a in MachineAssignment.query.filter_by(booking_id=b.id, completed_at=None).all():
        a.completed_at = now
    _free_machine(b.machine_id, b.id)
    audit(op, "WASH_COMPLETED", "booking", b.id)
    notify(b.student_id, "Wash completed", f"{ref_of(b)} is done. Please collect your clothes.", "COMPLETED", b.id)
    db.session.commit()
    return b


def mark_no_show(op, b):
    if b.status not in ("CONFIRMED",):
        raise ApiError("Only confirmed, not-yet-arrived appointments can be marked no-show", 409)
    deadline = tm.combine(b.booking_date, b.start_time) + timedelta(minutes=S.get_int("grace_period_minutes"))
    if tm.now_local() < deadline:
        raise ApiError(f"The {S.get_int('grace_period_minutes')}-minute grace period has not ended yet "
                       f"(until {deadline.strftime('%H:%M')})", 409)
    b.status = "NO_SHOW"
    audit(op, "NO_SHOW", "booking", b.id)
    notify(b.student_id, "Marked as no-show",
           f"You did not arrive within the grace period for {ref_of(b)}. No penalty was applied.", "NO_SHOW", b.id)
    db.session.commit()
    return b


def propose_reschedule(op, b, message):
    notify(b.student_id, "Please reschedule your appointment",
           f"{ref_of(b)}: {message or 'A machine is unavailable.'} Open My Bookings and request a new time.",
           "RESCHEDULE_PROPOSAL", b.id)
    audit(op, "RESCHEDULE_PROPOSED", "booking", b.id, message)
    db.session.commit()


# ---- rescheduling ---------------------------------------------------------------------
def request_reschedule(student, b: Booking, date_, start_time, reason):
    if b.student_id != student.id:
        raise ApiError("Booking not found", 404)
    if b.status != "CONFIRMED":
        raise ApiError("Only confirmed appointments can be rescheduled", 409)
    if RescheduleRequest.query.filter_by(booking_id=b.id, status="PENDING").first():
        raise ApiError("A rescheduling request is already pending", 409)
    sch.validate_slot(date_, start_time, b.duration_snapshot)
    sch.expire_reservations()
    sch.ensure_capacity(date_, start_time, b.duration_snapshot, exclude_id=b.id)
    end = tm.add_minutes(date_, start_time, b.duration_snapshot).time()
    r = RescheduleRequest(booking_id=b.id, original_date=b.booking_date, original_start_time=b.start_time,
                          original_end_time=b.end_time, requested_date=date_, requested_start_time=start_time,
                          requested_end_time=end, reason=(reason or "")[:300])
    db.session.add(r)
    db.session.flush()
    audit(student, "RESCHEDULE_REQUESTED", "reschedule", r.id)
    notify_operators("Reschedule request", f"{ref_of(b)} → {date_} {tm.hhmm(start_time)}", "RESCHEDULE_PENDING", b.id)
    db.session.commit()
    return r


def review_reschedule(op, r: RescheduleRequest, action, note):
    if r.status != "PENDING":
        raise ApiError("This request was already reviewed", 409)
    b = r.booking
    now = tm.now_local()
    if action == "approve":
        with sch.booking_lock():
            if b.status != "CONFIRMED":
                raise ApiError("The booking is no longer confirmed", 409)
            sch.validate_slot(r.requested_date, r.requested_start_time, b.duration_snapshot)
            sch.ensure_capacity(r.requested_date, r.requested_start_time, b.duration_snapshot, exclude_id=b.id)
            b.booking_date, b.start_time, b.end_time = r.requested_date, r.requested_start_time, r.requested_end_time
            b.machine_id, b.reminder_sent_at = None, None
            MachineAssignment.query.filter_by(booking_id=b.id, started_at=None).delete()
            r.status = "APPROVED"
            r.reviewed_by, r.reviewed_at, r.review_note = op.id, now, (note or "")[:300]
            audit(op, "RESCHEDULE_APPROVED", "reschedule", r.id)
            notify(b.student_id, "Reschedule approved",
                   f"{ref_of(b)} moved to {b.booking_date} at {tm.hhmm(b.start_time)}.", "RESCHEDULE_APPROVED", b.id)
            db.session.commit()
    elif action == "reject":
        r.status, r.reviewed_by, r.reviewed_at, r.review_note = "REJECTED", op.id, now, (note or "")[:300]
        audit(op, "RESCHEDULE_REJECTED", "reschedule", r.id)
        notify(b.student_id, "Reschedule rejected",
               f"{ref_of(b)} stays on {b.booking_date} at {tm.hhmm(b.start_time)}. {note or ''}".strip(),
               "RESCHEDULE_REJECTED", b.id)
        db.session.commit()
    else:
        raise ApiError("action must be 'approve' or 'reject'")
    return r
