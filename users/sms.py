# auth/sms.py
"""
Minimal Africa's Talking SMS client.

No third-party SDK. Just `requests` against AT's REST endpoint.
Docs: https://developers.africastalking.com/docs/sms/sending

The function never raises — a broken SMS provider must not break
registration or password-reset flows.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Configuration — override via Django settings or environment vars
# ------------------------------------------------------------------
# Priority: settings.AT_* > os.environ AT_* > built-in defaults.
# In production, use environment variables — never hardcode keys.

AT_USERNAME = getattr(
    settings, "AT_USERNAME", os.environ.get("AT_USERNAME", "bahi")
)
AT_API_KEY = getattr(
    settings,
    "AT_API_KEY",
    os.environ.get(
        "AT_API_KEY",
        "atsk_6dfbdde777d4e87a975bbb7447cf85628af5d12e8a401c34b750442f0897b0db970e67cb",
    ),
)
AT_SENDER_ID = getattr(
    settings, "AT_SENDER_ID", os.environ.get("AT_SENDER_ID", "")
)
AT_BASE_URL = getattr(
    settings,
    "AT_BASE_URL",
    os.environ.get(
        "AT_BASE_URL",
        "https://api.africastalking.com/version1/messaging",
    ),
)


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------

def _normalize_phone(phone: str) -> str:
    """
    Normalize a phone number into E.164-ish format required by AT.

    Handles:
      - 0712345678     → +255712345678  (Tanzania local)
      - 255712345678   → +255712345678
      - +255712345678  → +255712345678
      - spaces, dashes → stripped

    Assumes Tanzania (+255) when the number is local. Adjust the
    country-code logic if you serve multiple countries.
    """
    if not phone:
        return ""

    cleaned = "".join(c for c in str(phone).strip() if c.isdigit() or c == "+")

    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("255"):
        return "+" + cleaned
    if cleaned.startswith("0") and len(cleaned) >= 10:
        return "+255" + cleaned[1:]
    # Fallback: if it looks like a full number without leading 0
    if len(cleaned) >= 10:
        return "+" + cleaned
    return cleaned


def _recipient_list(phones: Iterable[str] | str) -> str:
    """
    AT expects recipients as a comma-separated string.
    Accepts either a single phone string or an iterable.
    """
    if isinstance(phones, str):
        items = [phones]
    else:
        items = list(phones)

    normalized = [_normalize_phone(p) for p in items if p]
    normalized = [p for p in normalized if p]
    return ",".join(normalized)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def send_sms(phone: str, message: str) -> bool:
    """
    Send a single SMS via Africa's Talking.

    Returns True if AT accepted the message, False otherwise.
    Never raises — logging captures the failure reason.
    """
    to = _normalize_phone(phone)
    if not to:
        logger.info("send_sms: empty phone, skipping")
        return False

    if not AT_API_KEY or not AT_USERNAME:
        logger.error("send_sms: AT credentials missing")
        return False

    payload = {
        "username": AT_USERNAME,
        "to": to,
        "message": message,
    }
    if AT_SENDER_ID:
        payload["from"] = AT_SENDER_ID

    headers = {
        "apiKey": AT_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        response = requests.post(
            AT_BASE_URL,
            data=payload,
            headers=headers,
            timeout=15,
        )
        if response.status_code >= 400:
            logger.error(
                "Africa's Talking SMS failed (%s) to %s: %s",
                response.status_code,
                to,
                response.text[:300],
            )
            return False

        # AT returns 200 with a body like:
        # { "SMSMessageData": { "Message": "Sent to 1/1 Total Cost: ...", ... } }
        try:
            body = response.json()
            summary = body.get("SMSMessageData", {}).get("Message", "")
        except Exception:
            summary = ""

        logger.info("SMS sent to %s — %s", to, summary or "ok")
        return True
    except requests.RequestException as exc:
        logger.exception("Africa's Talking SMS request failed: %s", exc)
        return False