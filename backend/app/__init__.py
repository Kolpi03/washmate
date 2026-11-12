import logging

from flask import Flask, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import cors, db, jwt
from app.utils.common import ApiError
from config import IS_PROD, Config, database_url

log = logging.getLogger("washmate")


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url()
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = Config.engine_options(app.config["SQLALCHEMY_DATABASE_URI"])
    app.config["IS_PROD"] = IS_PROD
    if overrides:
        app.config.update(overrides)
        if "SQLALCHEMY_DATABASE_URI" in overrides:
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = Config.engine_options(overrides["SQLALCHEMY_DATABASE_URI"])
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set in production")
    app.config["JWT_SECRET_KEY"] = app.config.get("JWT_SECRET_KEY") or app.config["SECRET_KEY"]

    db.init_app(app)
    jwt.init_app(app)
    origins = {app.config["FRONTEND_URL"].rstrip("/")}
    if not app.config["IS_PROD"]:
        origins |= {"http://localhost:5173", "http://127.0.0.1:5173"}
    origins = [o for o in origins if o]
    cors.init_app(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=True)

    from app.routes import auth, catalog, operations
    for m in (auth, catalog, operations):
        app.register_blueprint(m.bp)

    from app.utils.security import enforce_same_site_requests

    @app.before_request
    def _csrf_guard():
        if request.path.startswith("/api/"):
            enforce_same_site_requests()

    @app.errorhandler(ApiError)
    def api_error(e):
        db.session.rollback()
        extra = dict(e.extra)
        resp = jsonify({"error": e.message, **extra})
        if "retry_after" in extra:
            resp.headers["Retry-After"] = str(extra["retry_after"])
        return resp, e.status

    @app.errorhandler(IntegrityError)
    def integrity(e):
        db.session.rollback()
        return jsonify({"error": "That conflicts with existing data."}), 409

    @app.errorhandler(404)
    def nf(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def na(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(Exception)
    def unhandled(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify({"error": e.description}), e.code
        db.session.rollback()
        log.exception("Unhandled error on %s", request.path)
        return jsonify({"error": "Internal server error"}), 500

    @jwt.unauthorized_loader
    def _unauth(reason):
        return jsonify({"error": "Authentication required"}), 401

    @jwt.invalid_token_loader
    def _invalid(reason):
        return jsonify({"error": "Invalid session. Please log in again."}), 401

    @jwt.expired_token_loader
    def _expired(h, p):
        return jsonify({"error": "Session expired. Please log in again."}), 401

    @app.teardown_appcontext
    def _cleanup(exc):
        db.session.remove()

    if app.config.get("ENABLE_SCHEDULER") and not app.config.get("TESTING"):
        _start_scheduler(app)
    return app


def _start_scheduler(app):
    """Local/long-running servers only. On Vercel, /api/cron/reminders is used instead."""
    from apscheduler.schedulers.background import BackgroundScheduler

    def job():
        with app.app_context():
            from app.services.notifications import process_due_reminders
            from app.services.scheduling import expire_reservations
            try:
                expire_reservations()
                process_due_reminders()
            except Exception:
                log.exception("scheduler job failed")
                db.session.rollback()

    s = BackgroundScheduler(daemon=True)
    s.add_job(job, "interval", seconds=30, id="reminders", max_instances=1, coalesce=True)
    s.start()
