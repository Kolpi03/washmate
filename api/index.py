"""Vercel serverless entrypoint: exposes the Flask WSGI app. Schema creation is NOT done here
(run `python backend/manage.py init-db` once against the production DATABASE_URL)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app import create_app  # noqa: E402

app = create_app()
