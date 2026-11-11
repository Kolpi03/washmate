from app.utils import common as tm


def booking_dict(b, operator=False):
    now = tm.now_local()
    p = b.payment
    progress = None
    if b.status == "WASHING":
        from app.models import MachineAssignment
        a = (MachineAssignment.query.filter_by(booking_id=b.id, completed_at=None)
             .order_by(MachineAssignment.id.desc()).first())
        if a and a.started_at:
            progress = max(0, min(100, int((now - a.started_at).total_seconds() / 60 * 100 / b.duration_snapshot)))
    d = {
        "id": b.id, "booking_reference": b.booking_reference, "display_ref": b.booking_reference or f"REQ-{b.id}",
        "booking_date": b.booking_date.isoformat(), "start_time": tm.hhmm(b.start_time),
        "end_time": tm.hhmm(b.end_time), "wash_mode_id": b.wash_mode_id,
        "wash_mode": b.wash_mode.name if b.wash_mode else None,
        "duration_minutes": b.duration_snapshot, "price": float(b.price_snapshot),
        "water_litres": b.water_snapshot, "status": b.status, "payment_status": b.payment_status,
        "machine_id": b.machine_id, "machine_number": b.machine.machine_number if b.machine else None,
        "expires_at": tm.iso(b.expires_at), "confirmed_at": tm.iso(b.confirmed_at),
        "arrival_time": tm.iso(b.arrival_time), "completed_at": tm.iso(b.completed_at),
        "cancel_reason": b.cancel_reason, "created_at": tm.iso(b.created_at), "progress": progress,
        "payment_id": p.id if p else None, "transaction_reference": p.transaction_reference if p else None,
        "reject_reason": p.reject_reason if p else None,
    }
    if operator:
        d["student"] = {"id": b.student.id, "name": b.student.name, "roll_number": b.student.roll_number,
                        "hostel": b.student.hostel, "email": b.student.email}
    return d


def payment_dict(p):
    b = p.booking
    return {"id": p.id, "booking_id": b.id, "booking_ref": b.booking_reference or f"REQ-{b.id}",
            "student_name": b.student.name, "roll_number": b.student.roll_number,
            "transaction_reference": p.transaction_reference, "amount": float(p.amount),
            "payment_method": p.payment_method, "status": p.status, "reject_reason": p.reject_reason,
            "booking_date": b.booking_date.isoformat(), "start_time": tm.hhmm(b.start_time),
            "booking_status": b.status, "paid_at": tm.iso(p.paid_at), "verified_at": tm.iso(p.verified_at),
            "verified_by": p.verifier.name if p.verifier else None}


def reschedule_dict(r, operator=False):
    b = r.booking
    d = {"id": r.id, "booking_id": b.id, "booking_ref": b.booking_reference or f"REQ-{b.id}",
         "wash_mode": b.wash_mode.name, "duration_minutes": b.duration_snapshot, "original_date": r.original_date.isoformat(),
         "original_start_time": tm.hhmm(r.original_start_time), "original_end_time": tm.hhmm(r.original_end_time),
         "requested_date": r.requested_date.isoformat(), "requested_start_time": tm.hhmm(r.requested_start_time),
         "requested_end_time": tm.hhmm(r.requested_end_time), "reason": r.reason, "status": r.status,
         "review_note": r.review_note, "reviewed_at": tm.iso(r.reviewed_at), "created_at": tm.iso(r.created_at)}
    if operator:
        d["student_name"], d["roll_number"] = b.student.name, b.student.roll_number
    return d
