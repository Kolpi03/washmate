from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

# ---- enumerations (stored as strings) -------------------------------------------------
ROLE_STUDENT, ROLE_OPERATOR = "STUDENT", "OPERATOR"
MACHINE_STATUSES = ("AVAILABLE", "OCCUPIED", "MAINTENANCE", "INACTIVE")
WORKING_MACHINE = ("AVAILABLE", "OCCUPIED")
PAYMENT_STATUSES = ("PENDING", "VERIFIED", "REJECTED", "REFUNDED")
# RESERVED: capacity held, awaiting payment; PAYMENT_SUBMITTED: awaiting operator verification
BOOKING_STATUSES = ("RESERVED", "PAYMENT_SUBMITTED", "CONFIRMED", "ARRIVED", "WASHING",
                    "COMPLETED", "CANCELLED", "NO_SHOW", "REJECTED", "EXPIRED")
ACTIVE_BOOKING = ("RESERVED", "PAYMENT_SUBMITTED", "CONFIRMED", "ARRIVED", "WASHING")


def utcnow():
    """Hostel-local wall-clock time (name kept for column defaults)."""
    from app.utils import common as tm
    return tm.now_local()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    roll_number = db.Column(db.String(40), unique=True, nullable=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(12), nullable=False, default=ROLE_STUDENT)
    hostel = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "roll_number": self.roll_number, "email": self.email,
                "role": self.role, "hostel": self.hostel,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Machine(db.Model):
    __tablename__ = "machines"
    id = db.Column(db.Integer, primary_key=True)
    machine_number = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(12), nullable=False, default="AVAILABLE")
    maintenance_note = db.Column(db.String(300))
    maintenance_since = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (db.CheckConstraint("status IN ('AVAILABLE','OCCUPIED','MAINTENANCE','INACTIVE')",
                                         name="ck_machine_status"),)

    def to_dict(self):
        return {"id": self.id, "machine_number": self.machine_number, "status": self.status,
                "maintenance_note": self.maintenance_note,
                "maintenance_since": self.maintenance_since.isoformat() if self.maintenance_since else None,
                "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat()}


class WashMode(db.Model):
    __tablename__ = "wash_modes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.String(400), default="")
    duration_minutes = db.Column(db.Integer, nullable=False)
    water_litres = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (db.CheckConstraint("duration_minutes > 0", name="ck_mode_duration"),
                      db.CheckConstraint("price >= 0", name="ck_mode_price"),
                      db.CheckConstraint("water_litres >= 0", name="ck_mode_water"))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description,
                "duration_minutes": self.duration_minutes, "water_litres": self.water_litres,
                "price": float(self.price), "is_active": self.is_active}


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    booking_reference = db.Column(db.String(24), unique=True, nullable=True)  # assigned on confirmation
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    wash_mode_id = db.Column(db.Integer, db.ForeignKey("wash_modes.id"), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration_snapshot = db.Column(db.Integer, nullable=False)
    price_snapshot = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False)
    water_snapshot = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="RESERVED")
    payment_status = db.Column(db.String(12), nullable=False, default="PENDING")
    machine_id = db.Column(db.Integer, db.ForeignKey("machines.id"), nullable=True)
    expires_at = db.Column(db.DateTime)  # reservation hold deadline (RESERVED only)
    confirmed_at = db.Column(db.DateTime)
    reminder_sent_at = db.Column(db.DateTime)
    arrival_time = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    cancel_reason = db.Column(db.String(300))
    cancelled_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    student = db.relationship("User", foreign_keys=[student_id])
    wash_mode = db.relationship("WashMode")
    machine = db.relationship("Machine")
    payment = db.relationship("Payment", uselist=False, back_populates="booking")
    __table_args__ = (db.Index("ix_booking_date_status", "booking_date", "status"),)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, default="UPI")
    transaction_reference = db.Column(db.String(60), unique=True, nullable=True)
    status = db.Column(db.String(12), nullable=False, default="PENDING")
    reject_reason = db.Column(db.String(300))
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    paid_at = db.Column(db.DateTime)  # when the student submitted the reference
    verified_at = db.Column(db.DateTime)
    booking = db.relationship("Booking", back_populates="payment")
    verifier = db.relationship("User", foreign_keys=[verified_by])


class MachineAssignment(db.Model):
    __tablename__ = "machine_assignments"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, index=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machines.id"), nullable=False, index=True)
    assigned_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    machine = db.relationship("Machine")


class RescheduleRequest(db.Model):
    __tablename__ = "reschedule_requests"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, index=True)
    original_date = db.Column(db.Date, nullable=False)       # history of the appointment being replaced
    original_start_time = db.Column(db.Time, nullable=False)
    original_end_time = db.Column(db.Time, nullable=False)
    requested_date = db.Column(db.Date, nullable=False)
    requested_start_time = db.Column(db.Time, nullable=False)
    requested_end_time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.String(300))
    status = db.Column(db.String(12), nullable=False, default="PENDING")  # PENDING/APPROVED/REJECTED
    review_note = db.Column(db.String(300))
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    booking = db.relationship("Booking")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"))
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    notification_type = db.Column(db.String(30), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    scheduled_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)  # in-app delivery timestamp (no SMS/WhatsApp/email integration)

    def to_dict(self):
        return {"id": self.id, "booking_id": self.booking_id, "title": self.title, "message": self.message,
                "notification_type": self.notification_type, "is_read": self.is_read,
                "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
                "sent_at": self.sent_at.isoformat() if self.sent_at else None}


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(60), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(60), nullable=False)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    actor = db.relationship("User", foreign_keys=[actor_id])
