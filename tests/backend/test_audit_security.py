"""Regression tests for the production-quality security audit."""
import pytest

from conftest import DAY, book, confirmed, make_student, mode_id


# ---------- authorization sweep: every /api route is protected unless explicitly public ----------
PUBLIC = {"auth.register", "auth.login", "auth.logout", "auth.set_password_with_token", "ops.cron_reminders", "ops.health"}
STUDENT_OK = {"auth.me", "auth.update_me", "catalog.availability", "catalog.list_modes", "catalog.get_settings",
              "ops.create_booking", "ops.my_bookings", "ops.get_booking", "ops.cancel", "ops.pay_submit",
              "ops.resched_create", "ops.resched_list", "ops.notifications", "ops.notif_read", "ops.notif_read_all"}


def _routes(app):
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/api/") and rule.endpoint.split(".")[0] != "static":
            method = sorted(rule.methods - {"HEAD", "OPTIONS"})[0]
            yield rule, method, rule.rule.replace("<int:bid>", "1").replace("<int:mid>", "1") \
                .replace("<int:pid>", "1").replace("<int:rid>", "1").replace("<int:nid>", "1")


def test_every_route_requires_authentication(app, client):
    for rule, method, url in _routes(app):
        if rule.endpoint in PUBLIC:
            continue
        assert getattr(client, method.lower())(url, json={}).status_code == 401, (method, url)


def test_every_operator_route_rejects_students(app, student):
    for rule, method, url in _routes(app):
        if rule.endpoint in PUBLIC or rule.endpoint in STUDENT_OK:
            continue
        assert getattr(student, method.lower())(url, json={}).status_code == 403, (method, url)


def test_student_endpoints_do_not_expose_other_students_data(app, student, student2, op):
    b = confirmed(student, op, "10:00", ref="UTRPRIVACY001")
    assert student2.get(f"/api/bookings/{b['id']}").status_code == 404
    assert student2.patch(f"/api/bookings/{b['id']}/cancel", json={}).status_code == 404
    assert student2.post("/api/reschedule", json={"booking_id": b["id"], "requested_date": DAY,
                                                  "requested_start_time": "15:00"}).status_code == 404
    assert student2.get("/api/reschedule").json["requests"] == []
    assert "UTRPRIVACY001" not in student2.get("/api/notifications").get_data(as_text=True)


# ---------- malformed input must be a clean 4xx, never a 500 ----------
@pytest.mark.parametrize("payload", [[1, 2], "text", 5, None])
@pytest.mark.parametrize("path", ["/api/auth/register", "/api/auth/login", "/api/bookings", "/api/payments/submit",
                                  "/api/reschedule", "/api/machines", "/api/wash-modes", "/api/settings"])
def test_non_object_json_bodies_never_500(app, student, op, path, payload):
    c = op if path in ("/api/machines", "/api/wash-modes", "/api/settings") else student
    method = "patch" if path == "/api/settings" else "post"
    r = getattr(c, method)(path, json=payload)
    assert r.status_code < 500, (path, payload, r.status_code)


def test_reschedule_with_garbage_booking_id_is_400(student):
    r = student.post("/api/reschedule", json={"booking_id": "abc", "requested_date": DAY, "requested_start_time": "15:00"})
    assert r.status_code == 400


def test_null_bytes_are_rejected_not_stored(client):
    r = client.post("/api/auth/register", json={"name": "Bad\x00Name", "roll_number": "NUL1", "email": "n@x.io",
                                                "password": "Password123", "hostel": "H"})
    assert r.status_code == 400


def test_sql_injection_strings_are_inert(app, student, op):
    r = student.post("/api/auth/login", json={"email": "' OR 1=1 --", "password": "x' OR '1'='1"})
    assert r.status_code == 401
    assert student.get("/api/machines/availability?date=2026-11-16' OR 1=1--&wash_mode_id=1").status_code == 400
    assert op.get("/api/bookings?status=COMPLETED'; DROP TABLE users;--").status_code == 200
    assert op.get("/api/auth/me").status_code == 200  # tables intact


# ---------- passwords ----------
def test_password_policy(client):
    base = {"name": "A", "roll_number": "PW1", "email": "pw@x.io", "hostel": "H"}
    assert client.post("/api/auth/register", json={**base, "password": "x" * 129}).status_code == 400
    assert client.post("/api/auth/register", json={**base, "password": "pw@x.io"}).status_code == 400
    assert client.post("/api/auth/register", json={**base, "password": "12345678"}).status_code == 400
    assert client.post("/api/auth/register", json={**base, "password": "Password123"}).status_code == 201


# ---------- brute force / rate limiting ----------
def test_login_lockout_after_repeated_failures(app, client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "op@test.local", "password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1"})
    assert r.status_code == 429 and "Retry-After" in r.headers  # even the right password is refused while locked


def test_lockout_expires(app, client, clock):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "op@test.local", "password": "wrong"})
    clock.set(9, 20)  # 20 minutes later
    assert client.post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1"}).status_code == 200


def test_lockout_is_per_account_not_global(app, client):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "victim@x.io", "password": "wrong"})
    assert client.post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1"}).status_code == 200


def test_registration_is_rate_limited_per_ip(app):
    app.config["REGISTER_PER_IP_HOUR"] = 10     # production default is 30 (hostel Wi-Fi shares one IP)
    c = app.test_client()
    codes = [c.post("/api/auth/register", json={"name": "S", "roll_number": f"RL{i}", "email": f"rl{i}@x.io",
                                                "password": "Password123", "hostel": "H"}).status_code for i in range(14)]
    assert 429 in codes and codes[:5] == [201] * 5


# ---------- CSRF / cross-origin ----------
def test_cross_site_state_changing_request_is_blocked(app, student):
    r = student.post("/api/bookings", json={"wash_mode_id": 1, "booking_date": DAY, "start_time": "10:00"},
                     headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = student.post("/api/bookings", json={}, headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_same_origin_and_non_browser_requests_still_work(app, student):
    host = "http://localhost"
    assert book(student, "10:00").status_code == 201
    ok = student.post("/api/auth/logout", headers={"Origin": host})
    assert ok.status_code == 200


def test_cors_does_not_allow_localhost_in_production(tmp_path):
    from app import create_app
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'p.db'}", "SECRET_KEY": "x" * 40,
                      "FRONTEND_URL": "https://washmate-mu.vercel.app", "IS_PROD": True, "ENABLE_SCHEDULER": False})
    r = app.test_client().options("/api/auth/me", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert "Access-Control-Allow-Origin" not in r.headers
    r = app.test_client().options("/api/auth/me", headers={"Origin": "https://washmate-mu.vercel.app", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("Access-Control-Allow-Origin") == "https://washmate-mu.vercel.app"


# ---------- cron endpoint ----------
def test_cron_rejects_non_ascii_token_cleanly(client):
    r = client.get("/api/cron/reminders", headers={"Authorization": "Bearer pässword"})
    assert r.status_code == 401


def test_cron_disabled_when_secret_unset(tmp_path):
    from app import create_app
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'c.db'}", "SECRET_KEY": "x" * 40,
                      "CRON_SECRET": "", "ENABLE_SCHEDULER": False})
    assert app.test_client().get("/api/cron/reminders", headers={"Authorization": "Bearer "}).status_code == 401


# ---------- settings validation ----------
def test_settings_reject_unsafe_urls_and_bad_upi(op):
    assert op.patch("/api/settings", json={"upi_qr_code_url": "javascript:alert(1)"}).status_code == 400
    assert op.patch("/api/settings", json={"upi_qr_code_url": "https://cdn.example/qr.png"}).status_code == 200
    assert op.patch("/api/settings", json={"upi_id": "not a upi id"}).status_code == 400
    assert op.patch("/api/settings", json={"upi_id": "hostel@okbank"}).status_code == 200
    assert op.patch("/api/settings", json={"slot_interval_minutes": 0}).status_code == 400
    assert op.patch("/api/settings", json={"grace_period_minutes": 100000}).status_code == 400


def test_error_responses_do_not_leak_internals(client):
    r = client.post("/api/auth/login", data="{not json", content_type="application/json")
    body = r.get_data(as_text=True)
    assert r.status_code < 500 and "Traceback" not in body and "sqlalchemy" not in body.lower()
    assert mode_id


def test_operator_invite_link_sets_password_once(app):
    from app.extensions import db
    from app.models import User
    from app.routes.auth import make_setpw_token
    with app.app_context():
        u = User(email="new.op@test.local", name="New Op", role="OPERATOR", hostel="Laundry")
        u.set_password("random-unusable-string")
        db.session.add(u); db.session.commit()
        tok = make_setpw_token(u)
    c = app.test_client()
    assert c.post("/api/auth/set-password", json={"token": "junk", "password": "GoodPassw0rd!"}).status_code == 400
    assert c.post("/api/auth/set-password", json={"token": tok, "password": "short"}).status_code == 400
    assert c.post("/api/auth/set-password", json={"token": tok, "password": "GoodPassw0rd!"}).status_code == 200
    assert c.post("/api/auth/set-password", json={"token": tok, "password": "AnotherPassw0rd!"}).status_code == 400  # single use
    r = c.post("/api/auth/login", json={"email": "new.op@test.local", "password": "GoodPassw0rd!", "portal": "OPERATOR"})
    assert r.status_code == 200
