import logging
import os
from email.message import EmailMessage

import aiosmtplib

logger = logging.getLogger(__name__)


async def send_plain_email(*, to_addr: str, subject: str, body: str) -> None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    if not host:
        logger.warning("SMTP_HOST not set — email not sent (dev). To: %s Subject: %s", to_addr, subject)
        logger.info("Email body would be:\n%s", body)
        return

    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = (os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes"))
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    from_addr = (os.getenv("SMTP_FROM") or user or "noreply@localhost").strip()

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    await aiosmtplib.send(
        msg,
        hostname=host,
        port=port,
        username=user or None,
        password=password or None,
        start_tls=use_tls,
    )


async def send_verification_code_email(to_addr: str, code: str, purpose: str) -> None:
    if purpose == "registration":
        subject = "Подтверждение регистрации — SyharikTS"
        body = (
            f"Ваш код подтверждения: {code}\n\n"
            "Код действителен 15 минут.\n"
            "Если вы не регистрировались, проигнорируйте это письмо."
        )
    else:
        subject = "Сброс пароля — SyharikTS"
        body = (
            f"Ваш код для сброса пароля: {code}\n\n"
            "Код действителен 15 минут.\n"
            "Если вы не запрашивали сброс, проигнорируйте это письмо."
        )
    await send_plain_email(to_addr=to_addr, subject=subject, body=body)
