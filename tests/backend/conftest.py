import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

_OPS = Path(__file__).resolve().parent / "operators-test.txt"
_OPS.write_text("op@test.local\n")
os.environ["OPERATORS_FILE"] = str(_OPS)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.pop("DATABASE_URL", None)

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.utils import common as tm  # noqa: E402
from manage import create_operator, init_db  # noqa: E402

NOW = datetime(2026, 11, 16, 9, 0)  # a fixed Monday 09:00 "hostel time"
DAY = "2026-11-16"
TOMORROW = "2026-11-17"


class Clock:
    now = NOW

    @staticmethod
    def set(hh, mm=0, day=16):
        Clock.now = datetime(2026, 11, day, hh, mm)


@pytest.fixture
def clock(monkeypatch):
    Clock.now = NOW
    monkeypatch.setattr(tm, "now_local", lambda: Clock.now)
    return Clock


def _test_db_url(tmp_path):
    """SQLite by default. Set TEST_DATABASE_URL to run the suite on PostgreSQL – only a LOCAL throw-away
    database is accepted so tests can never touch a real/production database."""
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{tmp_path / 'test.db'}"
    for p in ("postgres://", "postgresql://"):
        if url.startswith(p):
            url = "postgresql+psycopg://" + url[len(p):]
    host = url.split("@")[-1].split("/")[0].split(":")[0]
    if host not in ("localhost", "127.0.0.1"):
        pytest.exit(f"Refusing to run tests against non-local database host '{host}'", returncode=2)
    return url


@pytest.fixture
def app(tmp_path, clock):
    url = _test_db_url(tmp_path)
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": url,
                      "SECRET_KEY": "test-secret-key-for-unit-tests-0123456789", "ENABLE_SCHEDULER": False,
                      "CRON_SECRET": "cron-test"})
    with app.app_context():
        if not url.startswith("sqlite"):
            db.drop_all()
        init_db(machines=3)
        create_operator("op@test.local", "OperatorPass1")
    yield app
    if not url.startswith("sqlite"):
        with app.app_context():
            db.session.remove()
            db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_student(app, n=1):
    c = app.test_client()
    r = c.post("/api/auth/register", json={"name": f"Student {n}", "roll_number": f"R{n:03d}",
                                           "email": f"s{n}@test.local", "password": "Password123", "hostel": "H1"})
    assert r.status_code == 201, r.json
    return c


@pytest.fixture
def student(app):
    return make_student(app, 1)


@pytest.fixture
def student2(app):
    return make_student(app, 2)


@pytest.fixture
def op(app):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1", "portal": "OPERATOR"})
    assert r.status_code == 200
    return c


def mode_id(c, name="Normal Wash"):
    return next(m["id"] for m in c.get("/api/wash-modes").json["wash_modes"] if m["name"] == name)


def book(c, start="10:00", date=DAY, mode="Normal Wash"):
    return c.post("/api/bookings", json={"wash_mode_id": mode_id(c, mode), "booking_date": date, "start_time": start})


def pay(c, bid, ref):
    return c.post("/api/payments/submit", json={"booking_id": bid, "transaction_reference": ref})


def confirmed(student, op, start="10:00", date=DAY, ref="UTR000111222", mode="Normal Wash"):
    b = book(student, start, date, mode).json["booking"]
    assert pay(student, b["id"], ref).status_code == 200
    pid = op.get("/api/payments/pending").json["payments"][-1]["id"]
    r = op.patch(f"/api/payments/{pid}/verify")
    assert r.status_code == 200, r.json
    return r.json["booking"]
