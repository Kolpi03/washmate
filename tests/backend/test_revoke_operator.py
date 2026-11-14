import pytest

from conftest import confirmed
from app.extensions import db
from app.models import AuditLog, Payment, User
from app.routes.auth import make_setpw_token
import manage


@pytest.fixture
def ops_file(tmp_path, monkeypatch):
    f = tmp_path / "operators.txt"
    f.write_text("# owner allowlist\nop@test.local\nsecond.op@test.local  # night shift\n")
    monkeypatch.setenv("OPERATORS_FILE", str(f))
    return f


def _add_second_operator(app):
    with app.app_context():
        manage.create_operator("second.op@test.local", "SecondPass1")


def _login(app, email, pw):
    return app.test_client().post("/api/auth/login", json={"email": email, "password": pw, "portal": "OPERATOR"})


def test_revoke_signs_out_blocks_login_and_keeps_history(app, student, op, ops_file):
    _add_second_operator(app)
    b = confirmed(student, op)  # payment verified by op@test.local
    assert op.get("/api/payments/pending").status_code == 200
    with app.app_context():
        manage.revoke_operator("OP@test.local")
        u = User.query.filter_by(email="op@test.local").one()
        assert u.role == "REVOKED"
        assert Payment.query.filter_by(verified_by=u.id).count() == 1  # history still linked
        assert AuditLog.query.filter_by(action="OPERATOR_REVOKED", entity_id=u.id).count() == 1
    assert op.get("/api/payments/pending").status_code == 401        # existing session cut off immediately
    assert op.get("/api/auth/me").status_code == 401
    assert _login(app, "op@test.local", "OperatorPass1").status_code == 401
    assert app.test_client().post("/api/auth/login", json={"email": "op@test.local", "password": "OperatorPass1"}).status_code == 401
    assert "op@test.local" not in manage.load_operator_emails(ops_file)
    assert "second.op@test.local" in ops_file.read_text() and "# owner allowlist" in ops_file.read_text()
    assert b["status"] == "CONFIRMED"


def test_revoke_voids_outstanding_invite_link(app, ops_file):
    _add_second_operator(app)
    with app.app_context():
        tok = make_setpw_token(User.query.filter_by(email="second.op@test.local").one())
        manage.revoke_operator("second.op@test.local")
    r = app.test_client().post("/api/auth/set-password", json={"token": tok, "password": "GoodPassw0rd!"})
    assert r.status_code == 400


def test_cannot_revoke_last_operator_without_force(app, ops_file):
    with app.app_context():
        with pytest.raises(SystemExit):
            manage.revoke_operator("op@test.local")
        assert User.query.filter_by(email="op@test.local").one().role == "OPERATOR"
        manage.revoke_operator("op@test.local", force=True)
        assert User.query.filter_by(email="op@test.local").one().role == "REVOKED"


def test_revoke_rejects_students_and_unknown_emails(app, student, ops_file):
    with app.app_context():
        for email in ("s1@test.local", "nobody@test.local"):
            with pytest.raises(SystemExit):
                manage.revoke_operator(email)
        assert User.query.filter_by(email="s1@test.local").one().role == "STUDENT"


def test_reinvite_reinstates_revoked_operator(app, ops_file, monkeypatch):
    _add_second_operator(app)
    sent = []
    monkeypatch.setattr("app.utils.mailer.send_mail", lambda to, subj, body: sent.append((to, body)))
    monkeypatch.setenv("SECRET_KEY", app.config["SECRET_KEY"])
    monkeypatch.setenv("FRONTEND_URL", "https://example.test")
    with app.app_context():
        manage.revoke_operator("second.op@test.local")
        ops_file.write_text(ops_file.read_text() + "second.op@test.local\n")  # owner re-adds them
        manage.invite_operators(only="second.op@test.local")
        assert User.query.filter_by(email="second.op@test.local").one().role == "OPERATOR"
    assert sent and sent[0][0] == "second.op@test.local"
    tok = sent[0][1].split("token=")[1].split()[0]
    c = app.test_client()
    assert c.post("/api/auth/set-password", json={"token": tok, "password": "GoodPassw0rd!"}).status_code == 200
    assert _login(app, "second.op@test.local", "GoodPassw0rd!").status_code == 200
