import threading

from conftest import DAY, TOMORROW, book, confirmed, make_student, mode_id, pay


def slot(c, start, mode="Normal Wash", date=DAY):
    s = c.get(f"/api/machines/availability?date={date}&wash_mode_id={mode_id(c, mode)}").json
    return next(x for x in s["slots"] if x["start_time"] == start)


def test_book_appointment_snapshots_and_reservation(student, op):
    r = book(student, "10:00")
    assert r.status_code == 201
    b = r.json["booking"]
    assert b["status"] == "RESERVED" and b["booking_reference"] is None
    assert (b["duration_minutes"], b["price"], b["water_litres"]) == (45, 30.0, 50)
    assert b["end_time"] == "10:45" and b["expires_at"]


def test_booking_validation(student):
    assert book(student, "07:00").status_code == 400            # before opening
    assert book(student, "19:30").status_code == 400            # would finish after closing
    assert book(student, "10:10").status_code == 400            # off the slot grid
    assert book(student, "08:30", date="2026-11-16").status_code == 400  # in the past (now 09:00)
    assert book(student, "10:00", date="2026-12-30").status_code == 400  # beyond advance window
    assert book(student, "10:00", date="garbage").status_code == 400


def test_capacity_calculation_and_overlap_prevention(app, student, op):
    # 3 machines. Fill them with overlapping bookings of different students.
    for i in range(3):
        c = make_student(app, 10 + i)
        assert book(c, "10:00").status_code == 201
    s = slot(student, "10:00")
    assert s["remaining"] == 0 and not s["available"]
    # 10:30 overlaps (Normal wash 10:00-10:45 + 10 min buffer => busy until 10:55)
    assert not slot(student, "10:30")["available"]
    assert book(student, "10:30").status_code == 409
    # 11:00 is free again (busy until 10:55)
    assert slot(student, "11:00")["remaining"] == 3
    assert book(student, "11:00").status_code == 201
    # a Quick Wash (25m) at 09:30 ends 09:55 + buffer 10:05 -> overlaps 10:00 start -> blocked
    assert not slot(student, "09:30", "Quick Wash")["available"]


def test_capacity_uses_real_durations_not_one_hour(app, student):
    # Quick (25m)+10m buffer frees its machine at 10:35; two Heavy (60m)+buffer jobs stay busy until 11:10.
    book(make_student(app, 20), "10:00", mode="Quick Wash")
    for n in (21, 22):
        book(make_student(app, n), "10:00", mode="Heavy Wash")
    assert not slot(student, "10:00")["available"]
    assert slot(student, "10:30", "Quick Wash")["remaining"] == 0   # quick job still busy until 10:35
    assert slot(student, "11:00", "Quick Wash")["remaining"] == 1   # exactly one machine free; not an hourly-slot model


def test_student_cannot_double_book_overlap(student):
    assert book(student, "10:00").status_code == 201
    assert book(student, "10:30").status_code == 409


def test_concurrent_booking_final_machine(app):
    op_c = app.test_client()
    op_c.post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1"})
    for m in op_c.get("/api/machines").json["machines"][1:]:
        op_c.patch(f"/api/machines/{m['id']}", json={"status": "MAINTENANCE"})
    clients = [make_student(app, 30 + i) for i in range(8)]
    results, barrier = [], threading.Barrier(8)

    def go(c):
        barrier.wait()
        results.append(book(c, "12:00").status_code)

    ts = [threading.Thread(target=go, args=(c,)) for c in clients]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count(201) == 1 and results.count(409) == 7, results


def test_reservation_expiry_releases_capacity(app, op, clock):
    for m in op.get("/api/machines").json["machines"][1:]:
        op.patch(f"/api/machines/{m['id']}", json={"status": "MAINTENANCE"})
    a, b = make_student(app, 40), make_student(app, 41)
    first = book(a, "13:00").json["booking"]
    assert book(b, "13:00").status_code == 409
    clock.set(9, 16)  # hold is 15 minutes
    assert book(b, "13:00").status_code == 201
    assert a.get(f"/api/bookings/{first['id']}").json["booking"]["status"] == "EXPIRED"
    assert pay(a, first["id"], "UTRLATE00001").status_code == 410


def test_payment_submission_and_verification_flow(student, op):
    b = book(student, "10:00").json["booking"]
    assert pay(student, b["id"], "x").status_code == 400
    r = pay(student, b["id"], "utr123456789")
    assert r.status_code == 200 and r.json["booking"]["status"] == "PAYMENT_SUBMITTED"
    assert r.json["booking"]["payment_status"] == "PENDING"  # NOT marked paid by the student's own claim
    pend = op.get("/api/payments/pending").json["payments"]
    assert len(pend) == 1 and pend[0]["transaction_reference"] == "UTR123456789"
    v = op.patch(f"/api/payments/{pend[0]['id']}/verify").json["booking"]
    assert v["status"] == "CONFIRMED" and v["payment_status"] == "VERIFIED"
    assert v["booking_reference"] == "WM-2026-001"
    notes = student.get("/api/notifications").json["notifications"]
    assert any(n["notification_type"] == "BOOKING_CONFIRMED" for n in notes)
    # second confirmed booking gets next unique reference
    assert confirmed(student, op, "12:00", ref="UTR999888777")["booking_reference"] == "WM-2026-002"


def test_duplicate_transaction_reference_rejected(app, student, op):
    other = make_student(app, 50)
    b1 = book(student, "10:00").json["booking"]
    b2 = book(other, "10:00").json["booking"]
    assert pay(student, b1["id"], "SAMEUTR12345").status_code == 200
    assert pay(other, b2["id"], "sameutr12345").status_code == 409


def test_reject_payment_releases_slot(app, student, op):
    for m in op.get("/api/machines").json["machines"][1:]:
        op.patch(f"/api/machines/{m['id']}", json={"status": "MAINTENANCE"})
    b = book(student, "10:00").json["booking"]
    pay(student, b["id"], "BADUTR123456")
    pid = op.get("/api/payments/pending").json["payments"][0]["id"]
    r = op.patch(f"/api/payments/{pid}/reject", json={"reason": "Not found in statement"})
    assert r.json["booking"]["payment_status"] == "REJECTED" and r.json["booking"]["status"] == "REJECTED"
    assert book(make_student(app, 51), "10:00").status_code == 201


def test_students_cannot_see_other_bookings(app, student, student2, op):
    b = book(student, "10:00").json["booking"]
    assert student2.get(f"/api/bookings/{b['id']}").status_code == 404
    assert student2.patch(f"/api/bookings/{b['id']}/cancel").status_code == 404
    assert pay(student2, b["id"], "STEALUTR12345").status_code == 404
    assert student2.get("/api/bookings/my").json["bookings"] == []
    assert op.get(f"/api/bookings/{b['id']}").status_code == 200


def test_reminders_generated_once_and_only_for_confirmed(app, student, student2, op, clock):
    c = confirmed(student, op, "10:00", ref="UTRREMIND0001")
    pending = book(student2, "10:00").json["booking"]  # never paid
    clock.set(9, 40)
    assert app.test_client().get("/api/cron/reminders").status_code == 401
    h = {"Authorization": "Bearer cron-test"}
    assert app.test_client().get("/api/cron/reminders", headers=h).json["reminders_sent"] == 0  # not yet 09:45
    clock.set(9, 45)
    cli = app.test_client()
    assert cli.get("/api/cron/reminders", headers=h).json["reminders_sent"] == 1
    assert cli.get("/api/cron/reminders", headers=h).json["reminders_sent"] == 0  # idempotent
    student.get("/api/notifications")  # lazy path must not duplicate either
    rem = [n for n in student.get("/api/notifications").json["notifications"] if n["notification_type"] == "REMINDER"]
    assert len(rem) == 1 and "15 minutes" in rem[0]["message"] and rem[0]["sent_at"]
    assert not [n for n in student2.get("/api/notifications").json["notifications"] if n["notification_type"] == "REMINDER"]
    nid = rem[0]["id"]
    assert student.patch(f"/api/notifications/{nid}/read").json["notification"]["is_read"] is True
    assert c["id"]


def test_cancelled_booking_gets_no_reminder(app, student, op, clock):
    b = confirmed(student, op, "10:00", ref="UTRCANCEL0001")
    assert student.patch(f"/api/bookings/{b['id']}/cancel", json={"reason": "plans changed"}).status_code == 200
    clock.set(9, 46)
    assert app.test_client().get("/api/cron/reminders", headers={"Authorization": "Bearer cron-test"}).json["reminders_sent"] == 0


def test_arrival_grace_and_no_show(student, op, clock):
    b = confirmed(student, op, "10:00", ref="UTRNOSHOW0001")
    clock.set(10, 5)
    early = op.patch(f"/api/bookings/{b['id']}/no-show")
    assert early.status_code == 409 and "grace" in early.json["error"].lower()
    clock.set(10, 11)
    r = op.patch(f"/api/bookings/{b['id']}/no-show")
    assert r.status_code == 200 and r.json["booking"]["status"] == "NO_SHOW"
    assert any(n["notification_type"] == "NO_SHOW" for n in student.get("/api/notifications").json["notifications"])
    assert r.json["booking"]["payment_status"] == "VERIFIED"  # no automatic financial penalty/refund change


def test_arrival_blocks_no_show(student, op, clock):
    b = confirmed(student, op, "10:00", ref="UTRARRIVE0001")
    clock.set(10, 3)
    assert op.patch(f"/api/bookings/{b['id']}/arrival").json["booking"]["status"] == "ARRIVED"
    clock.set(10, 30)
    assert op.patch(f"/api/bookings/{b['id']}/no-show").status_code == 409


def test_full_wash_lifecycle_and_machine_rules(app, student, op, clock):
    a = confirmed(student, op, "10:00", ref="UTRWASH000001")
    other = make_student(app, 60)
    b2 = book(other, "10:30").json["booking"]
    pay(other, b2["id"], "UTRWASH000002")
    op.patch(f"/api/payments/{op.get('/api/payments/pending').json['payments'][0]['id']}/verify")
    machines = op.get("/api/machines").json["machines"]
    m1 = machines[0]["id"]
    clock.set(10, 0)
    assert op.patch(f"/api/bookings/{a['id']}/start", json={"machine_id": m1}).status_code == 409  # not arrived
    op.patch(f"/api/bookings/{a['id']}/arrival")
    assert op.patch(f"/api/bookings/{a['id']}/assign", json={"machine_id": m1}).status_code == 200
    # overlapping appointment cannot reuse that machine
    op.patch(f"/api/bookings/{b2['id']}/arrival")
    assert op.patch(f"/api/bookings/{b2['id']}/assign", json={"machine_id": m1}).status_code == 409
    started = op.patch(f"/api/bookings/{a['id']}/start", json={})
    assert started.json["booking"]["status"] == "WASHING"
    assert next(m for m in op.get("/api/machines").json["machines"] if m["id"] == m1)["status"] == "OCCUPIED"
    assert op.patch(f"/api/machines/{m1}", json={"status": "MAINTENANCE"}).status_code == 409
    clock.set(10, 20)
    assert student.get(f"/api/bookings/{a['id']}").json["booking"]["progress"] == 44
    done = op.patch(f"/api/bookings/{a['id']}/complete").json["booking"]
    assert done["status"] == "COMPLETED"
    assert next(m for m in op.get("/api/machines").json["machines"] if m["id"] == m1)["status"] == "AVAILABLE"


def test_machine_breakdown_flags_but_never_cancels(app, student, op):
    # 3 machines; 3 confirmed overlapping bookings; take one machine down.
    cs = [student] + [make_student(app, 70), make_student(app, 71)]
    ids = [confirmed(c, op, "11:00", ref=f"UTRBREAK00000{i}")["id"] for i, c in enumerate(cs)]
    mid = op.get("/api/machines").json["machines"][0]["id"]
    out = op.patch(f"/api/machines/{mid}", json={"status": "MAINTENANCE"}).json
    assert len(out["at_risk_booking_ids"]) == 1 and out["at_risk_booking_ids"][0] in ids
    for i in ids:
        assert op.get(f"/api/bookings/{i}").json["booking"]["status"] == "CONFIRMED"  # not silently cancelled
    assert len(op.get("/api/bookings/at-risk").json["bookings"]) == 1
    risky = out["at_risk_booking_ids"][0]
    assert op.post(f"/api/bookings/{risky}/propose-reschedule", json={"message": "Machine under repair"}).status_code == 200
    assert not slot(student, "11:00")["available"] or slot(student, "11:00")["remaining"] == 0


def test_cancel_policy(student, op, clock):
    b = confirmed(student, op, "10:00", ref="UTRPOLICY0001")
    clock.set(9, 30)  # 30 min before start; cutoff is 60
    assert student.patch(f"/api/bookings/{b['id']}/cancel", json={}).status_code == 409
    assert op.patch(f"/api/bookings/{b['id']}/cancel", json={}).status_code == 400  # operator must give a reason
    r = op.patch(f"/api/bookings/{b['id']}/cancel", json={"reason": "Power cut", "refund": True})
    assert r.json["booking"]["status"] == "CANCELLED" and r.json["booking"]["payment_status"] == "REFUNDED"


def test_reschedule_request_approval(student, op):
    b = confirmed(student, op, "10:00", ref="UTRRESCH00001")
    r = student.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": TOMORROW,
                                              "requested_start_time": "15:00", "reason": "Lab session"})
    assert r.status_code == 201
    assert student.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": TOMORROW,
                                                 "requested_start_time": "16:00"}).status_code == 409  # one pending at a time
    rid = r.json["request"]["id"]
    ok = op.patch(f"/api/reschedule/{rid}", json={"action": "approve", "note": "ok"})
    assert ok.status_code == 200 and ok.json["request"]["status"] == "APPROVED"
    nb = student.get(f"/api/bookings/{b['id']}").json["booking"]
    assert (nb["booking_date"], nb["start_time"]) == (TOMORROW, "15:00")
    h = nb["reschedules"][0]  # history retained
    assert (h["original_date"], h["original_start_time"]) == (DAY, "10:00")
    assert op.patch(f"/api/reschedule/{rid}", json={"action": "approve"}).status_code == 409


def test_reschedule_rejection(student, op):
    b = confirmed(student, op, "10:00", ref="UTRRESCH00002")
    rid = student.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": TOMORROW,
                                                "requested_start_time": "15:00"}).json["request"]["id"]
    r = op.patch(f"/api/reschedule/{rid}", json={"action": "reject", "note": "Busy"})
    assert r.json["request"]["status"] == "REJECTED"
    nb = student.get(f"/api/bookings/{b['id']}").json["booking"]
    assert (nb["booking_date"], nb["start_time"]) == (DAY, "10:00")
    assert any(n["notification_type"] == "RESCHEDULE_REJECTED" for n in student.get("/api/notifications").json["notifications"])


def test_reschedule_into_full_slot_blocked_and_revalidated(app, student, op):
    for m in op.get("/api/machines").json["machines"][1:]:
        op.patch(f"/api/machines/{m['id']}", json={"status": "MAINTENANCE"})
    b = confirmed(student, op, "10:00", ref="UTRRESCH00003")
    blocker = make_student(app, 80)
    assert book(blocker, "15:00", TOMORROW).status_code == 201
    assert student.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": TOMORROW,
                                                 "requested_start_time": "15:00"}).status_code == 409
    rid = student.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": TOMORROW,
                                                "requested_start_time": "16:00"}).json["request"]["id"]
    assert book(blocker.__class__ and make_student(app, 81), "16:00", TOMORROW).status_code == 201  # slot gets taken meanwhile
    assert op.patch(f"/api/reschedule/{rid}", json={"action": "approve"}).status_code == 409


def test_wash_mode_price_change_keeps_old_snapshots(student, op):
    b = book(student, "10:00").json["booking"]
    op.patch(f"/api/wash-modes/{mode_id(op)}", json={"price": 99, "duration_minutes": 90})
    nb = student.get(f"/api/bookings/{b['id']}").json["booking"]
    assert (nb["price"], nb["duration_minutes"]) == (30.0, 45)


def test_reports_and_overview(student, op, clock):
    b = confirmed(student, op, "10:00", ref="UTRREPORT0001")
    clock.set(10, 0)
    op.patch(f"/api/bookings/{b['id']}/arrival")
    mid = op.get("/api/machines").json["machines"][0]["id"]
    op.patch(f"/api/bookings/{b['id']}/start", json={"machine_id": mid})
    clock.set(10, 45)
    op.patch(f"/api/bookings/{b['id']}/complete")
    r = op.get(f"/api/reports/daily?date={DAY}").json["report"]
    assert (r["total_bookings"], r["completed"], r["revenue"], r["estimated_water_litres"]) == (1, 1, 30.0, 50)
    assert r["popular_mode"] == "Normal Wash" and r["machine_utilization_pct"] > 0
    assert op.get(f"/api/reports/weekly?end={DAY}").json["report"]["total_bookings"] == 1
    assert op.get("/api/reports/monthly?month=2026-11").json["report"]["revenue"] == 30.0
    csv = op.get(f"/api/reports/daily?date={DAY}&format=csv")
    assert csv.mimetype == "text/csv" and b"verified_revenue" in csv.data
    ov = op.get("/api/reports/overview").json["overview"]
    assert ov["completed"] == 1 and ov["revenue_today"] == 30.0 and ov["machines"]["available"] == 3


def test_audit_logs_written(app, student, op):
    confirmed(student, op, "10:00", ref="UTRAUDIT00001")
    from app.models import AuditLog
    with app.app_context():
        actions = {a.action for a in AuditLog.query.all()}
    assert {"BOOKING_CREATED", "PAYMENT_SUBMITTED", "PAYMENT_VERIFIED"} <= actions
