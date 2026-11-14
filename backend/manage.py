"""Management CLI (safe, non-destructive).

  python backend/manage.py init-db                       create missing tables + default settings/modes/machines
  python backend/manage.py create-operator --email E     create/reset the operator (password prompted or OPERATOR_PASSWORD)
  python backend/manage.py invite-operators              email every address in operators.txt a set-your-password link
  python backend/manage.py revoke-operator --email E     disable an operator (history kept) and remove them from operators.txt
  python backend/manage.py seed-demo                     add a demo student (local/demo use only)
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from config import BASE_DIR, load_operator_emails  # noqa: E402
from app.models import ROLE_OPERATOR, ROLE_REVOKED, ROLE_STUDENT, Machine, User, WashMode  # noqa: E402
from app.utils.auth import audit  # noqa: E402

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


def invite_operators(only=None, resend=False):
    """Create (password-less) operator accounts for emails in operators.txt and email each a one-time link."""
    import secrets
    from app.routes.auth import make_setpw_token
    from app.utils.mailer import send_mail
    sk = os.environ.get("SECRET_KEY", "")
    if not sk or sk.startswith("[SENSITIVE") or sk == "dev-secret-change-me":
        sys.exit("SECRET_KEY is missing or a placeholder (e.g. '[SENSITIVE]' from `vercel env pull`). "
                 "Export the real production SECRET_KEY, or links will be rejected by the live app.")
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not base.startswith("http"):
        sys.exit("Set FRONTEND_URL (e.g. https://washmate-mu.vercel.app) so the email link points at the live app")
    for email in sorted(load_operator_emails()):
        if only and email != only.lower():
            continue
        u = User.query.filter_by(email=email).first()
        if u and u.role == ROLE_STUDENT:
            print("skip (student account):", email); continue
        if u and u.role == ROLE_REVOKED:  # the owner re-added a revoked operator to operators.txt
            u.role = ROLE_OPERATOR
            u.set_password(secrets.token_urlsafe(24))
            audit(None, "OPERATOR_REINSTATED", "user", u.id, "via manage.py invite-operators")
            db.session.commit()
            print("reinstated:", email)
        elif u and not resend:
            print("skip (already invited; use --resend):", email); continue
        if not u:
            u = User(email=email, name="Hostel Operator", role=ROLE_OPERATOR, hostel="Laundry")
            u.set_password(secrets.token_urlsafe(24))  # unusable until the invitee sets their own
            db.session.add(u)
            db.session.commit()
        link = f"{base}/operator/set-password?token={make_setpw_token(u)}"
        send_mail(email, "WashMate: set your operator password",
                  "You have been added as a WashMate operator.\n\nSet your password here (valid 48 hours, one use):\n"
                  f"{link}\n\nThen sign in at {base}/operator/login with this email.\n")
        print("invited:", email)


def _operators_file():
    from pathlib import Path
    return Path(os.environ.get("OPERATORS_FILE") or BASE_DIR / "operators.txt")


def remove_from_allowlist(email):
    """Drop `email` from operators.txt, keeping comments and other lines. Returns True if a line was removed."""
    path = _operators_file()
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return False
    kept = [l for l in lines if l.split("#")[0].strip().lower() != email]
    if len(kept) != len(lines):
        path.write_text("".join(kept), encoding="utf-8")
        return True
    return False


def revoke_operator(email, force=False):
    """Disable an operator account. The row is kept so payment/booking/audit history stays linked."""
    import secrets
    email = email.strip().lower()
    u = User.query.filter_by(email=email).first()
    if not u:
        sys.exit(f"No account with email {email}.")
    if u.role == ROLE_STUDENT:
        sys.exit(f"{email} is a student account, not an operator.")
    if u.role == ROLE_REVOKED:
        print("already revoked:", email)
    else:
        others = User.query.filter(User.role == ROLE_OPERATOR, User.id != u.id).count()
        if others == 0 and not force:
            sys.exit(f"{email} is the only operator; nobody could verify payments afterwards. Re-run with --force to revoke anyway.")
        u.role = ROLE_REVOKED
        u.set_password(secrets.token_urlsafe(32))  # also voids any outstanding set-password link
        audit(None, "OPERATOR_REVOKED", "user", u.id, "via manage.py revoke-operator")
        db.session.commit()
        print("revoked:", email, "(signed out everywhere; history kept)")
    if remove_from_allowlist(email):
        print("removed from", _operators_file().name)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    op = sub.add_parser("create-operator")
    op.add_argument("--email", default=os.environ.get("OPERATOR_EMAIL"))
    op.add_argument("--name", default="Hostel Operator")
    iv = sub.add_parser("invite-operators")
    iv.add_argument("--email", default=None)
    iv.add_argument("--resend", action="store_true")
    rv = sub.add_parser("revoke-operator")
    rv.add_argument("--email", required=True)
    rv.add_argument("--force", action="store_true", help="allow revoking the last remaining operator")
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
        elif a.cmd == "invite-operators":
            invite_operators(a.email, a.resend)
        elif a.cmd == "revoke-operator":
            revoke_operator(a.email, a.force)
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
