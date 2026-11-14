"""Minimal SMTP sender (Gmail by default). Configure SMTP_USER / SMTP_PASSWORD (app password) / MAIL_FROM."""
import os
import smtplib
import ssl
from email.message import EmailMessage


def send_mail(to, subject, body):
    user, pw = os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASSWORD", "")
    if not user or not pw:
        raise RuntimeError("SMTP_USER and SMTP_PASSWORD must be set to send email")
    msg = EmailMessage()
    msg["From"] = os.environ.get("MAIL_FROM") or user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    host, port = os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", "587"))
    ctx = ssl.create_default_context()
    if port == 465:  # implicit TLS (works on networks that break STARTTLS on 587)
        with smtplib.SMTP_SSL(host, port, timeout=20, context=ctx) as s:
            s.login(user, pw)
            s.send_message(msg)
        return
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.starttls(context=ctx)
        s.login(user, pw)
        s.send_message(msg)
