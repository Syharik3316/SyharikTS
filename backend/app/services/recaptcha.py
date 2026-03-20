import os
from typing import Optional

import requests


def verify_recaptcha_v2(*, token: str, remote_ip: Optional[str] = None) -> None:
    """
    Verifies ReCaptcha v2 token using Google `siteverify`.
    Raises ValueError on failure.
    """

    secret = (os.getenv("RECAPTCHA_V2_SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("RECAPTCHA_V2_SECRET_KEY is not configured")

    url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {
        "secret": secret,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    resp = requests.post(url, data=payload, timeout=15)
    try:
        data = resp.json()
    except Exception:
        raise ValueError("ReCaptcha verification failed (invalid response from verifier)")

    if not data.get("success"):
        # Avoid leaking too much details.
        raise ValueError("ReCaptcha verification failed")

