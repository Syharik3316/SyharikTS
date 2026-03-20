import os
import smtplib
from email.message import EmailMessage


def send_auth_code_email(*, to_email: str, subject: str, code: str) -> None:
    """
    Send email with auth code via SMTP.

    Required env:
      - SMTP_HOST, SMTP_PORT
      - SMTP_USER, SMTP_PASS
      - SMTP_FROM
    """

    host = (os.getenv("SMTP_HOST") or "").strip()
    port_raw = (os.getenv("SMTP_PORT") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    password = os.getenv("SMTP_PASS") or ""
    sender = (os.getenv("SMTP_FROM") or "").strip()

    if not host or not port_raw or not user or not sender:
        raise RuntimeError("SMTP is not configured (SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_FROM)")

    try:
        port = int(port_raw)
    except Exception as e:
        raise RuntimeError(f"SMTP_PORT must be int: {e}")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject

    # Keep message simple and clear.
    msg.set_content(
        f"Ваш код подтверждения: {code}\n\n"
        "Если вы не запрашивали код, просто проигнорируйте это письмо."
    )

    with smtplib.SMTP(host=host, port=port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

