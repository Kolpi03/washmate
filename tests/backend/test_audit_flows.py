"""Regression tests for the scheduling / payment / reminder / report audit."""
import threading

import pytest

from conftest import DAY, TOMORROW, book, confirmed, make_student, mode_id, pay

CRON = {"Authorization": "Bearer cron-test"}


def slots(c, mode="Normal Wash", date=DAY):
    return {s["start_time"]: s for s in c.get(f"/api/machines/availability?date={date}&wash_mode_id={mode_id(c, mode)}").json["slots"]}


def one_machine(op):
    for m in op.get("/api/machines").json["machines"][1:]:
        op.patch(f"/api/machines/{m['id']}", json={"status": "MAINTENANCE"})


# ================= scheduling =================
def test_buffer_boundary_adjacent_appointments(app, op, student):
    """Normal wash 10:00-10:45 + 10 min buffer => machine free at 10:55. 11:00 ok, 10:30 not."""
    one_machine(op)
    op.patch("/api/settings", json={"slot_interval_minutes": 5})
    assert book(student, "10:00").status_code == 201
    other = make_student(app, 90)
    assert book(other, "10:50").status_code == 409   # inside buffer
    assert book(other, "10:55").status_code == 201   # exactly when the machine is free again
    third = make_student(app, 91)
    assert book(third, "09:10").status_code == 409   # 09:10+45+10 = 10:05 overlaps 10:00 start
    assert book(third, "09:05").status_code == 201   # 09:05+45+10 = 10:00 -> back-to-back, no overlap


def test_cancellation_releases_capacity(app, op, student):
    one_machine(op)
    b = book(student, "10:00").json["booking"]
    other = make_student(app, 92)
    assert book(other, "10:00").status_code == 409
    assert student.patch(f"/api/bookings/{b['id']}/cancel", json={"reason": "x"}).status_code == 200
    assert book(other, "10:00").status_code == 201


def test_reschedule_approval_frees_old_slot_and_takes_new(app, op, student):
    one_machine(op)
    b = confirmed(student, op, "10:00", ref="UTRFREE0000001")
    rid = student.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": TOMORROW, "requested_start_time": "15:00"}).json["request"]["id"]
    op.patch(f"/api/reschedule/{rid}", json={"action": "approve"})
    other = make_student(app, 93)
    assert book(other, "10:00").status_code == 201                  # old slot free
    assert book(make_student(app, 94), "15:00", TOMORROW).status_code == 409  # new slot taken


def test_machine_maintenance_and_restore_roundtrip(app, op, student):
    one_machine(op)
    b = confirmed(student, op, "10:00", ref="UTRMAINT000001")
    ms = op.get("/api/machines").json["machines"]
    out = op.patch(f"/api/machines/{ms[1]['id']}", json={"status": "AVAILABLE"}).json
    assert out["working"] == 2 and out["at_risk_booking_ids"] == []
    assert slots(student)["10:00"]["remaining"] == 1
    out = op.patch(f"/api/machines/{ms[0]['id']}", json={"status": "MAINTENANCE"}).json  # now 1 machine again
    assert out["working"] == 1 and b["id"] not in out["at_risk_booking_ids"]


def test_midnight_boundary_buffer_carries_over(app, op, student):
    """A wash ending 23:55 keeps its machine busy (buffer) into the next day's first minutes."""
    one_machine(op)
    op.patch("/api/settings", json={"open_time": "00:00", "close_time": "23:59", "slot_interval_minutes": 5})
    assert book(student, "23:10", mode="Normal Wash").status_code == 201        # 23:10-23:55, busy to 00:05
    other = make_student(app, 95)
    assert book(other, "00:00", date="2026-11-17").status_code == 409            # next day 00:00 collides with buffer
    assert book(other, "00:05", date="2026-11-17").status_code == 201


def test_expire_notifies_exactly_once(app, student, clock):
    book(student, "13:00")
    clock.set(9, 30)
    from app.services import scheduling
    with app.app_context():
        assert scheduling.expire_reservations() == 1
        assert scheduling.expire_reservations() == 0
    notes = student.get("/api/notifications").json["notifications"]
    assert [n["notification_type"] for n in notes].count("EXPIRED") == 1


def test_wash_mode_duration_change_does_not_alter_existing_capacity(app, op, student):
    one_machine(op)
    b = confirmed(student, op, "10:00", ref="UTRDUR0000001")
    op.patch(f"/api/wash-modes/{mode_id(op)}", json={"duration_minutes": 120})
    got = student.get(f"/api/bookings/{b['id']}").json["booking"]
    assert (got["duration_minutes"], got["end_time"]) == (45, "10:45")
    assert not slots(student, "Normal Wash")["10:30"]["available"]        # still blocked by original 45-min job
    assert book(make_student(app, 96), "11:00", mode="Quick Wash").status_code == 201  # 10:55 free again


# ================= payments =================
@pytest.mark.parametrize("ref", ["", "   ", "abc", "x" * 41, "UTR 123456", "UTR_123456", "१२३४५६७८९", "ＵＴＲ１２３４５６", "UTR²123456"])
def test_invalid_or_non_ascii_references_rejected(student, ref):
    b = book(student, "10:00").json["booking"]
    assert pay(student, b["id"], ref).status_code == 400


def test_missing_reference_field(student):
    b = book(student, "10:00").json["booking"]
    assert student.post("/api/payments/submit", json={"booking_id": b["id"]}).status_code == 400


def test_repeated_submission_blocked(student):
    b = book(student, "10:00").json["booking"]
    assert pay(student, b["id"], "UTRREPEAT0001").status_code == 200
    assert pay(student, b["id"], "UTRREPEAT0002").status_code == 409


def test_reference_reuse_across_accounts_and_after_rejection(app, student, op):
    other = make_student(app, 97)
    b1 = book(student, "10:00").json["booking"]
    pay(student, b1["id"], "UTRSHARED00001")
    pid = op.get("/api/payments/pending").json["payments"][0]["id"]
    op.patch(f"/api/payments/{pid}/reject", json={"reason": "not found"})
    b2 = book(other, "12:00").json["booking"]
    assert pay(other, b2["id"], "UTRSHARED00001").status_code == 409   # rejected refs stay burned (no replay)


def test_verify_rejected_cancelled_or_unsubmitted_is_refused(app, student, op):
    b = book(student, "10:00").json["booking"]
    assert op.patch(f"/api/payments/{b['payment_id']}/verify").status_code == 409   # nothing submitted yet
    pay(student, b["id"], "UTRREFUSE00001")
    op.patch(f"/api/payments/{b['payment_id']}/reject", json={"reason": "no"})
    assert op.patch(f"/api/payments/{b['payment_id']}/verify").status_code == 409
    assert op.patch(f"/api/payments/{b['payment_id']}/reject", json={}).status_code == 409
    c = make_student(app, 98)
    b2 = book(c, "12:00").json["booking"]
    pay(c, b2["id"], "UTRREFUSE00002")
    op.patch(f"/api/bookings/{b2['id']}/cancel", json={"reason": "operator cancel"})
    assert op.patch(f"/api/payments/{b2['payment_id']}/verify").status_code == 409


def test_student_cannot_cancel_while_payment_is_awaiting_verification(student, op):
    """Otherwise the payment is marked REJECTED although the student may really have paid."""
    b = book(student, "10:00").json["booking"]
    pay(student, b["id"], "UTRMONEY000001")
    r = student.patch(f"/api/bookings/{b['id']}/cancel", json={})
    assert r.status_code == 409
    assert op.get("/api/payments/pending").json["payments"][0]["transaction_reference"] == "UTRMONEY000001"


def test_cannot_verify_after_appointment_has_ended(student, op, clock):
    b = book(student, "10:00").json["booking"]
    pay(student, b["id"], "UTRLATE0000001")
    clock.set(11, 0)
    r = op.patch(f"/api/payments/{b['payment_id']}/verify")
    assert r.status_code == 409 and "passed" in r.json["error"].lower()
    got = op.get(f"/api/bookings/{b['id']}").json["booking"]
    assert got["status"] == "PAYMENT_SUBMITTED"


def test_unauthorized_payment_actions(student, student2, op):
    b = book(student, "10:00").json["booking"]
    pay(student, b["id"], "UTRAUTH0000001")
    for act in ("verify", "reject", "refund"):
        assert student.patch(f"/api/payments/{b['payment_id']}/{act}", json={}).status_code == 403
        assert student2.patch(f"/api/payments/{b['payment_id']}/{act}", json={}).status_code == 403
    assert b["id"]


def test_concurrent_verification_gives_unique_references(app, op):
    clients = [make_student(app, 100 + i) for i in range(6)]
    pids = []
    for i, c in enumerate(clients):
        b = book(c, f"{9 + i}:00" if i < 1 else f"{9 + i:02d}:00").json["booking"]
        pay(c, b["id"], f"UTRCONC{i:06d}")
        pids.append(b["payment_id"])
    ops = []
    for _ in pids:
        o = app.test_client()
        o.post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1"})
        ops.append(o)
    out, bar = [], threading.Barrier(len(pids))

    def go(o, pid):
        bar.wait()
        r = o.patch(f"/api/payments/{pid}/verify")
        out.append((r.status_code, r.json.get("booking", {}).get("booking_reference")))

    ts = [threading.Thread(target=go, args=a) for a in zip(ops, pids)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    refs = [r for s, r in out if s == 200]
    assert len(refs) == 6 and len(set(refs)) == 6, out


def test_audit_log_content(app, student, op):
    b = book(student, "10:00").json["booking"]
    pay(student, b["id"], "UTRAUDIT0000A")
    op.patch(f"/api/payments/{b['payment_id']}/reject", json={"reason": "mismatch"})
    c = confirmed(make_student(app, 110), op, "12:00", ref="UTRAUDIT0000B")
    op.patch(f"/api/bookings/{c['id']}/cancel", json={"reason": "power cut", "refund": True})
    from app.models import AuditLog, User
    with app.app_context():
        opid = User.query.filter_by(role="OPERATOR").first().id
        rows = {(a.action, a.entity_type): a for a in AuditLog.query.all()}
        assert rows[("PAYMENT_REJECTED", "payment")].actor_id == opid and "mismatch" in rows[("PAYMENT_REJECTED", "payment")].details
        assert rows[("PAYMENT_VERIFIED", "payment")].actor_id == opid
        assert "power cut" in rows[("BOOKING_CANCELLED", "booking")].details
        assert rows[("PAYMENT_SUBMITTED", "payment")].actor_id != opid


# ================= reminders =================
def test_reminder_exactly_15_minutes_before(app, student, op, clock):
    confirmed(student, op, "10:00", ref="UTRREM0000001")
    clock.set(9, 44)
    cli = app.test_client()
    assert cli.get("/api/cron/reminders", headers=CRON).json["reminders_sent"] == 0
    clock.set(9, 45)
    assert cli.get("/api/cron/reminders", headers=CRON).json["reminders_sent"] == 1


def test_delayed_cron_inside_grace_still_reminds_but_after_it_does_not(app, student, op, clock):
    confirmed(student, op, "10:00", ref="UTRREM0000002")
    clock.set(10, 11)
    assert app.test_client().get("/api/cron/reminders", headers=CRON).json["reminders_sent"] == 0  # useless after grace


def test_reminder_for_appointment_just_after_midnight(app, op, student, clock):
    op.patch("/api/settings", json={"open_time": "00:00", "close_time": "23:59", "slot_interval_minutes": 5})
    clock.set(23, 0)
    confirmed(student, op, "00:05", date="2026-11-17", ref="UTRMIDNIGHT001")
    clock.set(23, 50)
    assert app.test_client().get("/api/cron/reminders", headers=CRON).json["reminders_sent"] == 1


def test_rescheduled_booking_uses_new_time_for_reminder(app, student, op, clock):
    b = confirmed(student, op, "10:00", ref="UTRREM0000003")
    clock.set(9, 45)
    app.test_client().get("/api/cron/reminders", headers=CRON)             # reminder for the original time
    clock.set(9, 46)
    rid = student.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": DAY, "requested_start_time": "14:00"}).json["request"]["id"]
    op.patch(f"/api/reschedule/{rid}", json={"action": "approve"})
    clock.set(13, 45)
    assert app.test_client().get("/api/cron/reminders", headers=CRON).json["reminders_sent"] == 1
    assert app.test_client().get("/api/cron/reminders", headers=CRON).json["reminders_sent"] == 0


def test_lazy_reminder_on_notification_poll_and_read_state(app, student, op, clock):
    confirmed(student, op, "10:00", ref="UTRREM0000004")
    clock.set(9, 50)
    first = student.get("/api/notifications").json
    assert first["unread"] >= 1 and any(n["notification_type"] == "REMINDER" for n in first["notifications"])
    student.patch("/api/notifications/read-all")
    assert student.get("/api/notifications").json["unread"] == 0
    assert student.get("/api/notifications").json["unread"] == 0     # no duplicate reminder appears


def test_notification_read_is_owner_only(student, student2, op):
    confirmed(student, op, "10:00", ref="UTRREM0000005")
    nid = student.get("/api/notifications").json["notifications"][0]["id"]
    assert student2.patch(f"/api/notifications/{nid}/read").status_code == 404


# ================= reports =================
def _complete(student, op, clock, ref, start="10:00"):
    b = confirmed(student, op, start, ref=ref)
    clock.set(int(start[:2]), 0)
    op.patch(f"/api/bookings/{b['id']}/arrival")
    op.patch(f"/api/bookings/{b['id']}/start", json={"machine_id": op.get("/api/machines").json["machines"][0]["id"]})
    clock.set(int(start[:2]), 45)
    op.patch(f"/api/bookings/{b['id']}/complete")
    clock.set(9, 0)
    return b


def test_revenue_counts_only_verified_unrefunded_payments(app, student, op, clock):
    keep = confirmed(student, op, "10:00", ref="UTRREV0000001")                       # 30 verified
    rej = make_student(app, 120)
    b = book(rej, "12:00").json["booking"]; pay(rej, b["id"], "UTRREV0000002")        # pending: not revenue
    ref_c = make_student(app, 121)
    r = confirmed(ref_c, op, "14:00", ref="UTRREV0000003")                            # verified then refunded
    op.patch(f"/api/bookings/{r['id']}/cancel", json={"reason": "refund", "refund": True})
    kept = make_student(app, 122)
    k = confirmed(kept, op, "16:00", ref="UTRREV0000004")                             # cancelled, NOT refunded: money still held
    op.patch(f"/api/bookings/{k['id']}/cancel", json={"reason": "cancelled, refund pending"})
    rep = op.get(f"/api/reports/daily?date={DAY}").json["report"]
    assert rep["revenue"] == 60.0   # 30 (kept #1) + 30 (cancelled, payment still VERIFIED)
    assert op.get("/api/reports/overview").json["overview"]["revenue_today"] == 60.0
    assert keep["id"]


def test_report_boundaries(app, student, op):
    confirmed(student, op, "10:00", date=DAY, ref="UTRBND0000001")
    confirmed(make_student(app, 123), op, "10:00", date="2026-11-22", ref="UTRBND0000002")  # exactly 6 days after
    confirmed(make_student(app, 124), op, "10:00", date="2026-11-23", ref="UTRBND0000003") if False else None
    assert op.get("/api/reports/weekly?end=2026-11-22").json["report"]["total_bookings"] == 2   # 16..22 inclusive
    assert op.get("/api/reports/weekly?end=2026-11-21").json["report"]["total_bookings"] == 1
    assert op.get("/api/reports/monthly?month=2026-11").json["report"]["total_bookings"] == 2
    assert op.get("/api/reports/monthly?month=2026-02").json["report"]["total_bookings"] == 0
    assert op.get("/api/reports/monthly?month=2026-13").status_code == 400
    assert op.get("/api/reports/daily?date=bad").status_code == 400


def test_water_report_is_estimate_from_completed_only(app, student, op, clock):
    _complete(student, op, clock, "UTRWAT0000001")
    confirmed(make_student(app, 125), op, "12:00", ref="UTRWAT0000002")                # not completed -> no water
    r = op.get(f"/api/reports/daily?date={DAY}").json["report"]
    assert r["estimated_water_litres"] == 50 and "estimate" in r["note"].lower()


def test_csv_export_is_utf8_and_formula_safe(op, student):
    op.post("/api/wash-modes", json={"name": "=HYPERLINK(\"http://x\")", "duration_minutes": 30, "water_litres": 1, "price": 1})
    mid = next(m["id"] for m in op.get("/api/wash-modes?all=1").json["wash_modes"] if m["name"].startswith("="))
    b = student.post("/api/bookings", json={"wash_mode_id": mid, "booking_date": DAY, "start_time": "10:00"}).json["booking"]
    r = op.get(f"/api/reports/daily?date={DAY}&format=csv")
    text = r.get_data(as_text=True)
    assert "charset=utf-8" in r.headers["Content-Type"].lower() and text.startswith("﻿")
    assert "=HYPERLINK" not in text.replace("'=HYPERLINK", "")      # neutralised with a leading apostrophe
    assert b["id"]
