from functools import wraps

from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions import db
from app.models import AuditLog, User
from app.utils.common import ApiError


def current_user() -> User:
    verify_jwt_in_request()
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        raise ApiError("Account no longer exists", 401)
    return user


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            user = current_user()
            if roles and user.role not in roles:
                raise ApiError("You do not have permission to perform this action", 403)
            return fn(user, *a, **kw)
        return wrapper
    return deco


login_required = role_required()
operator_required = role_required("OPERATOR")
student_required = role_required("STUDENT")


def audit(actor, action, entity_type, entity_id=None, details=""):
    db.session.add(AuditLog(actor_id=actor.id if actor else None, action=action,
                            entity_type=entity_type, entity_id=entity_id, details=str(details)[:2000]))
