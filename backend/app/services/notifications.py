from app.extensions import db
from app.models import Booking, Notification, User
from app.services import settings as S
from app.utils import common as tm

REMINDER_TEXT = ("Your washing appointment is scheduled in 15 minutes. "
                 "Please report to the hostel washing machine area at your booked time.")


def notify(user_id, title, message, ntype, booking_id=None, scheduled_at=None):
    n = Notification(user_id=user_id, booking_id=booking_id, title=title, message=message[:500],
                     notification_type=ntype, scheduled_at=scheduled_at, sent_at=tm.now_local())
    db.session.add(n)
    return n


def notify_operators(title, message, ntype, booking_id=None):
    for op in User.query.filter_by(role="OPERATOR").all():
        notify(op.id, title, message, ntype, booking_id)


def process_due_reminders():
    """Idempotent: creates one in-app reminder for each CONFIRMED appointment entering its reminder window.
    Safe to call from cron, from a scheduler thread, and lazily on API reads."""
    now = tm.now_local()
    lead = S.get_int("reminder_minutes_before")
    from datetime import timedelta
    q = (Booking.query.filter(Booking.status == "CONFIRMED", Booking.reminder_sent_at.is_(None),
                              Booking.booking_date == now.date()))
    sent = 0
    for b in q.with_for_update(skip_locked=True).all() if db.engine.dialect.name == "postgresql" else q.all():
        start = tm.combine(b.booking_date, b.start_time)
        if start - timedelta(minutes=lead) <= now < start + timedelta(minutes=S.get_int("grace_period_minutes")):
            b.reminder_sent_at = now
            msg = REMINDER_TEXT.replace("15 minutes", f"{lead} minutes")
            notify(b.student_id, "Appointment reminder", msg, "REMINDER", b.id,
                   scheduled_at=start - timedelta(minutes=lead))
            sent += 1
    db.session.commit()
    return sent
