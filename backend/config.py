import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ON_VERCEL = bool(os.environ.get("VERCEL"))
IS_PROD = os.environ.get("FLASK_ENV", "development").lower() == "production" or ON_VERCEL


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        if ON_VERCEL:
            raise RuntimeError("DATABASE_URL must be set on Vercel (SQLite is not persistent there).")
        inst = BASE_DIR / "instance"
        inst.mkdir(exist_ok=True)
        return f"sqlite:///{inst / 'washmate.db'}"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or ("dev-secret-change-me" if not IS_PROD else None)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    JWT_TOKEN_LOCATION = ["cookies", "headers"]
    JWT_COOKIE_SECURE = IS_PROD
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = False  # SameSite=Lax + JSON-only API; cookie is HttpOnly
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    CRON_SECRET = os.environ.get("CRON_SECRET", "")
    DEFAULT_UPI_ID = os.environ.get("UPI_ID", "")
    DEFAULT_UPI_QR = os.environ.get("UPI_QR_CODE_URL", "")
    TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")
    ENABLE_SCHEDULER = (not ON_VERCEL) and os.environ.get("ENABLE_SCHEDULER", "1") == "1"

    @staticmethod
    def engine_options(url: str):
        if url.startswith("sqlite"):
            return {"connect_args": {"check_same_thread": False, "timeout": 30}}
        return {"pool_pre_ping": True, "pool_recycle": 280, "pool_size": 3, "max_overflow": 2}
