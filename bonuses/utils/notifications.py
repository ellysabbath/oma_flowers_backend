# utils/notifications.py
"""
Payment NOTIFICATION helpers — SMS text only.

These functions are called AFTER a payment has already been recorded in
the system (`status='paid'`). They do NOT initiate or process payments.
They simply inform the recipient and the admin team via SMS.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model

from .sms import send_sms

logger = logging.getLogger(__name__)
User = get_user_model()


def _fmt_money(amount) -> str:
    try:
        return f"TSh {Decimal(str(amount)):,.0f}"
    except Exception:
        return str(amount)


def _fmt_date(value) -> str:
    if not value:
        return ""
    try:
        return value.strftime("%d %b %Y")
    except Exception:
        return str(value)


def _admin_phone() -> Optional[str]:
    configured = getattr(settings, "ADMIN_PAYMENT_PHONE", None)
    if configured:
        return configured
    try:
        admin = (
            User.objects.filter(is_superuser=True)
            .exclude(phone__isnull=True)
            .exclude(phone="")
            .order_by("id")
            .first()
        )
        return getattr(admin, "phone", None) if admin else None
    except Exception as exc:
        logger.warning("[notify] Could not resolve admin phone: %s", exc)
        return None


def _user_phone(obj) -> Optional[str]:
    if obj is None:
        return None
    user = getattr(obj, "user", None)
    if user is not None:
        return getattr(user, "phone", None)
    return getattr(obj, "phone", None)


def _user_name(obj) -> str:
    user = getattr(obj, "user", obj)
    return (
        getattr(user, "full_name", None)
        or getattr(user, "get_full_name", lambda: "")()
        or getattr(user, "username", None)
        or getattr(user, "email", None)
        or "Customer"
    )


def notify_bonus_paid(bonus) -> dict:
    results = {"user": None, "admin": None}
    if bonus is None:
        return results

    amount = _fmt_money(getattr(bonus, "amount", 0))
    name = getattr(bonus, "name", "Bonus")
    period = " ".join(
        filter(None, [
            getattr(bonus, "month", ""),
            str(getattr(bonus, "year", "") or ""),
        ])
    )
    paid_on = _fmt_date(getattr(bonus, "payment_date", None))
    dist = getattr(bonus, "distributor", None)

    user_phone = _user_phone(dist)
    if user_phone:
        user_msg = (
            f"Hello {_user_name(dist)},\n"
            f"Your {name}"
            f"{(' for ' + period) if period else ''} of {amount} "
            f"has been PAID"
            f"{(' on ' + paid_on) if paid_on else ''}. "
            f"Thank you for your work with OMA Flowers."
        )
        results["user"] = send_sms(user_phone, user_msg)

    admin_phone = _admin_phone()
    if admin_phone:
        admin_msg = (
            f"[OMA ADMIN] Bonus PAID: {name} — {amount} "
            f"to {_user_name(dist)}"
            f"{(' on ' + paid_on) if paid_on else ''}."
        )
        results["admin"] = send_sms(admin_phone, admin_msg)

    return results


def notify_commission_paid(commission) -> dict:
    results = {"user": None, "admin": None}
    if commission is None:
        return results

    amount = _fmt_money(getattr(commission, "amount", 0))
    ctype = (getattr(commission, "type", None) or "Commission").title()
    paid_on = _fmt_date(getattr(commission, "payment_date", None))
    dist = getattr(commission, "distributor", None)

    user_phone = _user_phone(dist)
    if user_phone:
        results["user"] = send_sms(
            user_phone,
            f"Hello {_user_name(dist)},\n"
            f"Your {ctype} commission of {amount} has been PAID"
            f"{(' on ' + paid_on) if paid_on else ''}. "
            f"Thank you for your work with OMA Flowers.",
        )

    admin_phone = _admin_phone()
    if admin_phone:
        results["admin"] = send_sms(
            admin_phone,
            f"[OMA ADMIN] Commission PAID: {ctype} — {amount} "
            f"to {_user_name(dist)}.",
        )

    return results


def notify_order_paid(order) -> dict:
    results = {"user": None, "admin": None}
    if order is None:
        return results

    amount = _fmt_money(getattr(order, "total_amount", 0))
    number = getattr(order, "order_number", getattr(order, "id", ""))
    user_obj = getattr(order, "user", None) or getattr(order, "customer", None)

    user_phone = _user_phone(user_obj)
    if user_phone:
        results["user"] = send_sms(
            user_phone,
            f"Hello {_user_name(user_obj)},\n"
            f"Payment confirmed for order #{number} — {amount}. "
            f"Thank you for shopping with OMA Flowers.",
        )

    admin_phone = _admin_phone()
    if admin_phone:
        results["admin"] = send_sms(
            admin_phone,
            f"[OMA ADMIN] Order #{number} PAID — {amount}.",
        )

    return results


def notify_admin_payment(user, amount, reference, kind: str = "Payment") -> dict:
    admin_phone = _admin_phone()
    if not admin_phone:
        return {"ok": False, "error": "No admin phone configured."}
    return send_sms(
        admin_phone,
        f"[OMA ADMIN] {kind} PAID — {_fmt_money(amount)} "
        f"to {_user_name(user)} (ref: {reference}).",
    )