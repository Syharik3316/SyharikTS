import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def verify_recaptcha_v2(token: str | None) -> bool:
    """
    Verify reCAPTCHA v2 with Google siteverify.
    RECAPTCHA_SECRET_KEY must be set; otherwise verification fails (production-safe).
    """
    secret = (os.getenv("RECAPTCHA_SECRET_KEY") or "").strip()
    if not secret:
        logger.error("RECAPTCHA_SECRET_KEY is not set — reCAPTCHA verification rejected")
        return False
    if not token or not str(token).strip():
        return False
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": token.strip()},
        )
    if r.status_code != 200:
        logger.warning("reCAPTCHA siteverify HTTP %s", r.status_code)
        return False
    data = r.json()
    return bool(data.get("success"))
