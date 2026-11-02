# auth/utils.py
"""
Email + SMS utilities for OMA Flowers.

Every verification-code path (register, resend, password reset,
verify email, verify reset) goes through this module so there is
exactly one place that:

  - generates codes
  - invalidates stale ones
  - sends email
  - sends SMS via Africa's Talking
  - notifies users of admin-initiated account changes

Every send function is fire-and-forget: a mail or SMS outage never
breaks registration, login, password reset, or any admin action.

Both the email and SMS bodies for verification codes include the
user's OMA ID so it's immediately usable for login.
"""

from __future__ import annotations

import logging
import random
import string
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import User, VerificationCode
from .sms import send_sms

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Tunables
# ------------------------------------------------------------------

CODE_LENGTH = 6
CODE_TTL_MINUTES = 30

EMAIL_TYPES = {
    "email": {
        "subject": "Verify Your OMA Flowers Account",
        "intro": "Thank you for registering with OMA Flowers.",
        "instruction": "Enter the code below to verify your email address.",
        "resend_subject": "Your New OMA Flowers Verification Code",
        "resend_intro": "Here is your new verification code.",
    },
    "password_reset": {
        "subject": "Password Reset - OMA Flowers",
        "intro": "We received a request to reset your password.",
        "instruction": "Enter the code below to reset your password.",
        "resend_subject": "Your New OMA Flowers Password Reset Code",
        "resend_intro": "Here is your new password reset code.",
    },
}

# SMS bodies stay short to avoid multi-segment billing. These fit in
# one 160-char segment on most carriers.
SMS_BODIES = {
    "email": (
        "OMA Flowers\n"
        "User ID: {user_id}\n"
        "Code: {code}\n"
        "Valid {mins} min. Do not share."
    ),
    "password_reset": (
        "OMA Flowers password reset\n"
        "User ID: {user_id}\n"
        "Code: {code}\n"
        "Valid {mins} min. Do not share."
    ),
}


# ------------------------------------------------------------------
# Core primitives
# ------------------------------------------------------------------

def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join(random.choices(string.digits, k=length))


def invalidate_old_codes(user: User, code_type: str) -> int:
    return VerificationCode.objects.filter(
        user=user,
        type=code_type,
        is_used=False,
    ).update(is_used=True)


def create_verification_code(
    user: User,
    code_type: str = "email",
    code: Optional[str] = None,
    ttl_minutes: int = CODE_TTL_MINUTES,
) -> VerificationCode:
    invalidate_old_codes(user, code_type)
    return VerificationCode.objects.create(
        user=user,
        code=code or generate_code(),
        type=code_type,
        expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
    )


# ------------------------------------------------------------------
# Email rendering + send
# ------------------------------------------------------------------

def _render_email_body(
    code_type: str, code: str, user_id: str, is_resend: bool
) -> str:
    cfg = EMAIL_TYPES.get(code_type, EMAIL_TYPES["email"])
    intro = cfg["resend_intro"] if is_resend else cfg["intro"]

    # Only show the "your new User ID" block on the very first send —
    # the user already has it on resends.
    id_block = (
        ""
        if is_resend
        else (
            "Your OMA User ID (keep this safe — you can log in with it):\n"
            f"  {user_id}\n\n"
        )
    )

    return (
        f"{intro}\n\n"
        f"{id_block}"
        f"Your verification code is: {code}\n\n"
        f"{cfg['instruction']}\n\n"
        f"This code expires in {CODE_TTL_MINUTES} minutes.\n\n"
        f"If you did not request this, you can safely ignore this email.\n\n"
        f"— OMA Flowers"
    )


def send_verification_email(
    user: User,
    code: str,
    code_type: str = "email",
    is_resend: bool = False,
) -> bool:
    if not getattr(user, "email", None):
        logger.info("send_verification_email: user %s has no email", user.pk)
        return False

    cfg = EMAIL_TYPES.get(code_type, EMAIL_TYPES["email"])
    subject = cfg["resend_subject"] if is_resend else cfg["subject"]
    body = _render_email_body(
        code_type, code, getattr(user, "user_id", "") or "", is_resend
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(
            "Verification email (%s) sent to %s (user_id=%s)",
            code_type, user.email, user.user_id,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to send verification email (%s) to %s: %s",
            code_type, user.email, exc,
        )
        return False


# ------------------------------------------------------------------
# SMS rendering + send (verification codes)
# ------------------------------------------------------------------

def _render_sms_body(code_type: str, code: str, user_id: str) -> str:
    template = SMS_BODIES.get(code_type, SMS_BODIES["email"])
    return template.format(
        code=code, mins=CODE_TTL_MINUTES, user_id=user_id or "—"
    )


def send_verification_sms(
    user: User,
    code: str,
    code_type: str = "email",
) -> bool:
    phone = (
        getattr(user, "phone", None)
        or getattr(user, "mobile_number", None)
    )
    if not phone:
        logger.info(
            "send_verification_sms: user %s has no phone, skipping", user.pk,
        )
        return False

    message = _render_sms_body(
        code_type, code, getattr(user, "user_id", "") or ""
    )
    sent = send_sms(phone, message)
    if sent:
        logger.info(
            "Verification SMS (%s) sent to %s (user_id=%s)",
            code_type, phone, user.user_id,
        )
    return sent


# ------------------------------------------------------------------
# High-level helpers — verification codes
# ------------------------------------------------------------------

def issue_verification_code(
    user: User,
) -> Tuple[VerificationCode, bool, bool]:
    """Email-verification flow: fresh code → email + SMS."""
    verification = create_verification_code(user, code_type="email")
    email_sent = send_verification_email(user, verification.code, "email")
    sms_sent = send_verification_sms(user, verification.code, "email")

    if not email_sent and not sms_sent:
        logger.error(
            "Verification code delivered on NO channel for user %s", user.pk,
        )
    return verification, email_sent, sms_sent


def issue_password_reset_code(
    user: User,
) -> Tuple[VerificationCode, bool, bool]:
    verification = create_verification_code(user, code_type="password_reset")
    email_sent = send_verification_email(
        user, verification.code, "password_reset"
    )
    sms_sent = send_verification_sms(
        user, verification.code, "password_reset"
    )

    if not email_sent and not sms_sent:
        logger.error(
            "Password reset code delivered on NO channel for user %s",
            user.pk,
        )
    return verification, email_sent, sms_sent


def resend_verification_code(
    user: User,
) -> Tuple[VerificationCode, bool, bool]:
    verification = create_verification_code(user, code_type="email")
    email_sent = send_verification_email(
        user, verification.code, "email", is_resend=True
    )
    sms_sent = send_verification_sms(user, verification.code, "email")

    if not email_sent and not sms_sent:
        logger.error(
            "Resent verification code delivered on NO channel for user %s",
            user.pk,
        )
    return verification, email_sent, sms_sent


# ------------------------------------------------------------------
# Verify helper
# ------------------------------------------------------------------

def verify_code(
    user: User,
    code: str,
    code_type: str = "email",
) -> Tuple[bool, str]:
    """
    Returns (ok, reason):
      - (True,  "")              → valid, consumed
      - (False, "invalid_code")  → not found / already used
      - (False, "expired")       → past TTL
    """
    verification = VerificationCode.objects.filter(
        user=user,
        code=code,
        type=code_type,
        is_used=False,
    ).first()

    if not verification:
        logger.warning(
            "No valid %s code for %s (submitted=%s)",
            code_type, user.email, code,
        )
        return False, "invalid_code"

    if not verification.is_valid():
        logger.warning(
            "Expired %s code for %s (expired_at=%s)",
            code_type, user.email, verification.expires_at,
        )
        return False, "expired"

    verification.is_used = True
    verification.save(update_fields=["is_used"])
    return True, ""


# ==================================================================
# Admin-action notifications
# ==================================================================
# Every admin action that changes a user's role or account status
# sends a short SMS notification to that user.
#
# Design:
#   * Fire-and-forget — never raises, never blocks the admin action.
#   * One template per event type so wording stays consistent.
#   * If the user has no phone on file, the function is a no-op.
#   * Uses the same Africa's Talking client as verification codes.
#   * Keep every body <= ~150 chars to avoid multi-segment billing.

ADMIN_NOTIFICATION_BODIES = {
    "role_changed": (
        "OMA Flowers: your account role has been changed to {role} "
        "by an administrator. If unexpected, contact support."
    ),
    "promoted_admin": (
        "OMA Flowers: you have been promoted to ADMIN. Sign in to review "
        "your new permissions. Contact support if this was unexpected."
    ),
    "promoted_distributor": (
        "OMA Flowers: your account has been upgraded to DISTRIBUTOR. "
        "Sign in to access your distributor dashboard."
    ),
    "demoted_customer": (
        "OMA Flowers: your account has been set to CUSTOMER. Sign in for "
        "details. Contact support if this was unexpected."
    ),
    "activated": (
        "OMA Flowers: your account has been ACTIVATED. You can now sign in."
    ),
    "deactivated": (
        "OMA Flowers: your account has been DEACTIVATED. Contact support "
        "if you need help restoring access."
    ),
    "banned": (
        "OMA Flowers: your account has been BANNED. Contact support for "
        "more information."
    ),
    "unbanned": (
        "OMA Flowers: your account has been UNBANNED. You can sign in again."
    ),
    "email_verified": (
        "OMA Flowers: your email address has been verified by an "
        "administrator. No action needed."
    ),
    "password_reset_by_admin": (
        "OMA Flowers: your password was reset by an administrator.\n"
        "New password: {password}\n"
        "Sign in with this password and change it immediately."
    ),
}


def _user_phone(user: User) -> str:
    return str(
        getattr(user, "phone", None)
        or getattr(user, "mobile_number", None)
        or ""
    ).strip()


def notify_user_sms(
    user: User,
    template_key: str,
    **kwargs,
) -> bool:
    """
    Send a plain SMS notification to `user` using a named template.

    Returns True if the message was accepted by the SMS provider,
    False otherwise (missing phone, missing template, provider error,
    or any unexpected exception). Never raises.
    """
    try:
        template = ADMIN_NOTIFICATION_BODIES.get(template_key)
        if not template:
            logger.warning(
                "notify_user_sms: unknown template '%s' for user %s",
                template_key, getattr(user, "pk", "?"),
            )
            return False

        phone = _user_phone(user)
        if not phone:
            logger.info(
                "notify_user_sms: user %s has no phone, skipping '%s'",
                user.pk, template_key,
            )
            return False

        message = template.format(**kwargs)
        sent = send_sms(phone, message)
        if sent:
            logger.info(
                "Admin-notification SMS (%s) sent to %s (user_id=%s)",
                template_key, phone, getattr(user, "user_id", "?"),
            )
        else:
            logger.warning(
                "Admin-notification SMS (%s) FAILED for user %s (%s)",
                template_key, user.pk, phone,
            )
        return sent
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "notify_user_sms(%s) crashed for user %s: %s",
            template_key, getattr(user, "pk", "?"), exc,
        )
        return False


# ------------------------------------------------------------------
# Convenience wrappers — one per admin event
# ------------------------------------------------------------------

def notify_role_changed(user: User, new_role: str) -> bool:
    """Send the correct SMS for a role transition."""
    role = (new_role or "").lower()
    if role == "admin":
        return notify_user_sms(user, "promoted_admin")
    if role == "distributor":
        return notify_user_sms(user, "promoted_distributor")
    if role == "customer":
        return notify_user_sms(user, "demoted_customer")
    return notify_user_sms(
        user, "role_changed", role=role.upper() or "UNKNOWN"
    )


def notify_account_activated(user: User) -> bool:
    return notify_user_sms(user, "activated")


def notify_account_deactivated(user: User) -> bool:
    return notify_user_sms(user, "deactivated")


def notify_account_banned(user: User) -> bool:
    return notify_user_sms(user, "banned")


def notify_account_unbanned(user: User) -> bool:
    return notify_user_sms(user, "unbanned")


def notify_email_verified(user: User) -> bool:
    return notify_user_sms(user, "email_verified")


def notify_password_reset_by_admin(user: User, new_password: str) -> bool:
    """
    Send the admin-reset password to the user via SMS so they can
    immediately log in. `new_password` is required.

    Never raises. Returns True if the SMS was accepted by the provider.
    """
    return notify_user_sms(
        user, "password_reset_by_admin", password=new_password
    )


def notify_status_changed(user: User, new_status: str) -> bool:
    """Dispatch an SMS based on a status transition."""
    s = (new_status or "").lower()
    if s == "banned":
        return notify_account_banned(user)
    if s == "active":
        return notify_account_activated(user)
    if s == "inactive":
        return notify_account_deactivated(user)
    # pending / other — no specific notification
    return False