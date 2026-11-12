import re

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies

from app.extensions import db
from app.models import User
from app.utils.auth import audit, login_required
from app.utils.common import ApiError, json_body
from app.utils import security
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


_DUMMY_HASH = generate_password_hash("not-a-real-password")  # equalises timing for unknown accounts


def check_password_policy(pw, *identifiers):
    if len(pw) < 8:
        raise ApiError("Password must be at least 8 characters")
    if len(pw) > 128:
        raise ApiError("Password must be at most 128 characters")
    if pw.isdigit() or len(set(pw)) == 1:
        raise ApiError("Choose a less guessable password (not only digits or one repeated character)")
    low = pw.lower()
    if any(i and low == i.lower() for i in identifiers):
        raise ApiError("Password must not be the same as your email, roll number or name")


def _clean(data, key, maxlen, required=True):
    v = str((data or {}).get(key, "") or "").strip()
    if required and not v:
        raise ApiError(f"{key.replace('_', ' ').capitalize()} is required")
    if len(v) > maxlen:
        raise ApiError(f"{key.replace('_', ' ').capitalize()} is too long")
    return v


@bp.post("/register")
def register():
    d = json_body()
    name, roll = _clean(d, "name", 120), _clean(d, "roll_number", 40).upper()
    email, hostel = _clean(d, "email", 160).lower(), _clean(d, "hostel", 80)
    pw = str(d.get("password", ""))
    if not EMAIL.match(email):
        raise ApiError("Enter a valid email address")
    check_password_policy(pw, email, roll, name)
    security.check_registration_allowed()
    if User.query.filter_by(email=email).first():
        raise ApiError("An account with this email already exists", 409)
    if User.query.filter_by(roll_number=roll).first():
        raise ApiError("An account with this roll number already exists", 409)
    u = User(name=name, roll_number=roll, email=email, hostel=hostel, role="STUDENT")  # role is never client-controlled
    u.set_password(pw)
    db.session.add(u)
    db.session.flush()
    audit(u, "STUDENT_REGISTERED", "user", u.id, f"ip:{security.client_ip()}")
    db.session.commit()
    resp = jsonify({"user": u.to_dict()})
    set_access_cookies(resp, create_access_token(identity=str(u.id)))
    return resp, 201


@bp.post("/login")
def login():
    d = json_body()
    ident = str(d.get("email", "")).strip().lower()
    portal = str(d.get("portal", "")).upper()
    security.check_login_allowed(ident)
    u = User.query.filter_by(email=ident).first() or User.query.filter_by(roll_number=ident.upper()).first()
    pw = str(d.get("password", ""))
    if u:
        good = u.check_password(pw)
    else:
        check_password_hash(_DUMMY_HASH, pw)
        good = False
    if not good:
        security.record_login_failure(ident)
        raise ApiError("Invalid credentials", 401)
    if portal in ("STUDENT", "OPERATOR") and u.role != portal:
        raise ApiError("Invalid credentials for this portal", 401)
    if u.role == "OPERATOR" and u.email.lower() not in current_app.config.get("OPERATOR_EMAILS", set()):
        raise ApiError("Invalid credentials", 401)  # operator removed from backend/operators.txt
    resp = jsonify({"user": u.to_dict()})
    set_access_cookies(resp, create_access_token(identity=str(u.id)))
    return resp


@bp.post("/logout")
def logout():
    resp = jsonify({"message": "Logged out"})
    unset_jwt_cookies(resp)
    return resp


@bp.get("/me")
@login_required
def me(user):
    return jsonify({"user": user.to_dict()})


@bp.patch("/me")
@login_required
def update_me(user):
    d = json_body()
    if "name" in d:
        user.name = _clean(d, "name", 120)
    if "hostel" in d:
        user.hostel = _clean(d, "hostel", 80)
    if "email" in d:
        email = _clean(d, "email", 160).lower()
        if not EMAIL.match(email):
            raise ApiError("Enter a valid email address")
        if User.query.filter(User.email == email, User.id != user.id).first():
            raise ApiError("Email already in use", 409)
        user.email = email
    if "roll_number" in d and user.role == "STUDENT":
        roll = _clean(d, "roll_number", 40).upper()
        if User.query.filter(User.roll_number == roll, User.id != user.id).first():
            raise ApiError("Roll number already in use", 409)
        user.roll_number = roll
    db.session.commit()
    return jsonify({"user": user.to_dict()})
