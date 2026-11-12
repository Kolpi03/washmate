"""Management CLI (safe, non-destructive).

  python backend/manage.py init-db                       create missing tables + default settings/modes/machines
  python backend/manage.py create-operator --email E     create/reset the operator (password prompted or OPERATOR_PASSWORD)
  python backend/manage.py seed-demo                     add a demo student (local/demo use only)
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from config import load_operator_emails  # noqa: E402
from app.models import Machine, User, WashMode  # noqa: E402

# Clearly ILLUSTRATIVE starting values – the operator edits these in the portal.
DEFAULT_MODES = [
    ("Soak Wash", "Pre-soak followed by a gentle wash for stained clothes.", 75, 70, 40),
    ("Normal Wash", "Standard wash cycle for everyday clothes.", 45, 50, 30),
    ("Quick Wash", "Short cycle for lightly worn clothes.", 25, 35, 20),
    ("Heavy Wash", "Extended cycle for blankets and heavy fabrics.", 60, 80, 50),
]


def init_db(machines=6):
    db.create_all()  # only creates missing tables; never drops
    if WashMode.query.count() == 0:
        for n, d, dur, w, p in DEFAULT_MODES:
            db.session.add(WashMode(name=n, description=d, duration_minutes=dur, water_litres=w, price=p))
    if Machine.query.count() == 0:
        for i in range(1, machines + 1):
            db.session.add(Machine(machine_number=f"M{i}", status="AVAILABLE"))
    db.session.commit()


def create_operator(email, password, name="Hostel Operator"):
    if email.lower() not in load_operator_emails():
        sys.exit(f"{email} is not in backend/operators.txt - only the app owner can authorise operators by adding the email there.")
    u = User.query.filter_by(email=email.lower()).first()
    if u and u.role != "OPERATOR":
        sys.exit("That email belongs to a student account.")
    if not u:
        u = User(email=email.lower(), name=name, role="OPERATOR", hostel="Laundry")
        db.session.add(u)
    u.set_password(password)
    db.session.commit()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    op = sub.add_parser("create-operator")
    op.add_argument("--email", default=os.environ.get("OPERATOR_EMAIL"))
    op.add_argument("--name", default="Hostel Operator")
    dm = sub.add_parser("seed-demo")
    dm.add_argument("--email", default="demo.student@washmate.test")
    dm.add_argument("--password", default="DemoStudent#2026")
    a = ap.parse_args()
    app = create_app()
    with app.app_context():
        init_db()
        if a.cmd == "create-operator":
            if not a.email:
                sys.exit("--email (or OPERATOR_EMAIL) required")
            pw = os.environ.get("OPERATOR_PASSWORD") or getpass.getpass("Operator password (min 8 chars): ")
            if len(pw) < 8:
                sys.exit("Password too short")
            create_operator(a.email, pw, a.name)
            print("Operator ready:", a.email)
        elif a.cmd == "seed-demo":
            if not User.query.filter_by(email=a.email).first():
                u = User(name="Demo Student", roll_number="DEMO001", email=a.email, role="STUDENT", hostel="Hall Demo")
                u.set_password(a.password)
                db.session.add(u)
                db.session.commit()
            print("Demo student:", a.email)
        else:
            print("Database initialised.")


if __name__ == "__main__":
    main()
