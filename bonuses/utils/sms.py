# utils/sms.py
"""
Low-level SMS sender via Africa's Talking.

This module sends TEXT MESSAGES only. It does NOT move money.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 10 and digits.startswith("0"):
        return f"+255{digits[1:]}"
    if len(digits) == 12 and digits.startswith("255"):
        return f"+{digits}"
    if len(digits) == 9:
        return f"+255{digits}"
    return None


def _config() -> dict:
    return {
        "username": getattr(settings, "AT_USERNAME", ""),
        "api_key": getattr(settings, "AT_API_KEY", ""),
        "sender_id": getattr(settings, "AT_SENDER_ID", None),
        "base_url": getattr(
            settings,
            "AT_BASE_URL",
            "https://api.africastalking.com/version1/messaging",
        ),
    }


def send_sms(phone: str, message: str) -> dict:
    return send_sms_bulk([phone], message)


def send_sms_bulk(phones: Iterable[str], message: str) -> dict:
    cfg = _config()

    if not cfg["username"] or not cfg["api_key"]:
        logger.warning("[sms] AT credentials not configured.")
        return {"ok": False, "error": "SMS provider not configured."}

    if not message or not message.strip():
        return {"ok": False, "error": "Empty message."}

    normalized, seen = [], set()
    for p in phones:
        n = _normalize_phone(p)
        if n and n not in seen:
            normalized.append(n)
            seen.add(n)

    if not normalized:
        return {"ok": False, "error": "No valid phone numbers."}

    payload = {
        "username": cfg["username"],
        "to": ",".join(normalized),
        "message": message.strip(),
    }
    if cfg["sender_id"]:
        payload["from"] = cfg["sender_id"]

    headers = {
        "apiKey": cfg["api_key"],
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        resp = requests.post(
            cfg["base_url"], data=payload, headers=headers, timeout=15
        )
        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if resp.status_code >= 400:
            logger.error("[sms] HTTP %s: %s", resp.status_code, data)
            return {"ok": False, "error": f"HTTP {resp.status_code}", "raw": data}

        recipients = data.get("SMSMessageData", {}).get("Recipients", []) or []
        delivered = [r for r in recipients if r.get("status") == "Success"]

        logger.info("[sms] Delivered %d/%d.", len(delivered), len(normalized))
        return {
            "ok": len(delivered) > 0 or not recipients,
            "recipients": recipients,
            "raw": data,
        }

    except requests.RequestException as exc:
        logger.exception("[sms] Request failed: %s", exc)
        return {"ok": False, "error": str(exc)}