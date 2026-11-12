from conftest import mode_id


def test_student_registration_and_validation(client):
    ok = client.post("/api/auth/register", json={"name": "A", "roll_number": "r1", "email": "a@x.io",
                                                 "password": "Password123", "hostel": "H"})
    assert ok.status_code == 201 and ok.json["user"]["role"] == "STUDENT"
    assert "password" not in str(ok.json).lower()
    dup = client.post("/api/auth/register", json={"name": "B", "roll_number": "R2", "email": "a@x.io",
                                                  "password": "Password123", "hostel": "H"})
    assert dup.status_code == 409
    weak = client.post("/api/auth/register", json={"name": "B", "roll_number": "R3", "email": "b@x.io",
                                                   "password": "short", "hostel": "H"})
    assert weak.status_code == 400


def test_cannot_self_register_as_operator(client):
    r = client.post("/api/auth/register", json={"name": "Evil", "roll_number": "E1", "email": "e@x.io",
                                                "password": "Password123", "hostel": "H", "role": "OPERATOR"})
    assert r.json["user"]["role"] == "STUDENT"


def test_student_login_and_session(student):
    r = student.get("/api/auth/me")
    assert r.status_code == 200 and r.json["user"]["email"] == "s1@test.local"
    student.post("/api/auth/logout")
    assert student.get("/api/auth/me").status_code == 401


def test_login_wrong_password_and_portal_mismatch(app, client):
    assert client.post("/api/auth/login", json={"email": "op@test.local", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1",
                                                "portal": "STUDENT"}).status_code == 401


def test_operator_login(op):
    assert op.get("/api/auth/me").json["user"]["role"] == "OPERATOR"


def test_passwords_hashed(app):
    from app.models import User
    with app.app_context():
        assert all("Password" not in u.password_hash and u.password_hash for u in User.query.all())


def test_role_authorization(student, op):
    for method, url in [("get", "/api/machines"), ("post", "/api/machines"), ("get", "/api/bookings"),
                        ("get", "/api/payments/pending"), ("get", "/api/reports/daily"), ("patch", "/api/settings"),
                        ("post", "/api/wash-modes")]:
        assert getattr(student, method)(url, json={}).status_code == 403, url
    assert op.post("/api/bookings", json={}).status_code == 403  # operators cannot book as students


def test_unauthorized_api_access(client):
    for url in ["/api/bookings/my", "/api/machines", "/api/wash-modes", "/api/notifications", "/api/settings"]:
        assert client.get(url).status_code == 401, url


def test_wash_mode_create_and_modify(op, student):
    r = op.post("/api/wash-modes", json={"name": "Delicate", "description": "d", "duration_minutes": 35,
                                         "water_litres": 40, "price": 25})
    assert r.status_code == 201
    mid = r.json["wash_mode"]["id"]
    assert op.post("/api/wash-modes", json={"name": "Delicate", "duration_minutes": 35, "water_litres": 40,
                                            "price": 25}).status_code == 409
    assert op.patch(f"/api/wash-modes/{mid}", json={"price": 28, "duration_minutes": 40}).json["wash_mode"]["price"] == 28
    assert op.post("/api/wash-modes", json={"name": "Bad", "duration_minutes": 0, "water_litres": 1, "price": 1}).status_code == 400
    op.patch(f"/api/wash-modes/{mid}", json={"is_active": False})
    assert "Delicate" not in [m["name"] for m in student.get("/api/wash-modes").json["wash_modes"]]


def test_machine_creation_and_status(op):
    r = op.post("/api/machines", json={"machine_number": "M9"})
    assert r.status_code == 201
    assert op.post("/api/machines", json={"machine_number": "M9"}).status_code == 409
    mid = r.json["machine"]["id"]
    out = op.patch(f"/api/machines/{mid}", json={"status": "MAINTENANCE", "maintenance_note": "drum noise"})
    assert out.json["machine"]["status"] == "MAINTENANCE" and out.json["working"] == 3
    assert op.patch(f"/api/machines/{mid}", json={"status": "BROKEN"}).status_code == 400
    assert op.patch(f"/api/machines/{mid}", json={"status": "AVAILABLE"}).json["working"] == 4


def test_settings_defaults_and_validation(op, student):
    assert op.get("/api/settings").json["settings"]["grace_period_minutes"] == "10"
    assert "cron" not in str(student.get("/api/settings").json).lower()
    assert op.patch("/api/settings", json={"grace_period_minutes": "abc"}).status_code == 400
    assert op.patch("/api/settings", json={"open_time": "21:00"}).status_code == 400
    assert op.patch("/api/settings", json={"upi_id": "hostel@upi"}).json["settings"]["upi_id"] == "hostel@upi"
    assert mode_id(student)
