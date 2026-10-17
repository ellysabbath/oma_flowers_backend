# auth/utils.py
"""
Email + SMS code utilities for OMA Flowers.

Every verification-code path (register, resend, password reset,
verify email, verify reset) goes through this module so there is
exactly one place that:

  - generates codes
  - invalidates stale ones
  - sends email
  - sends SMS via Africa's Talking

Every send function is fire-and-forget: a mail or SMS outage never
breaks registration, login, or password reset.
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

# SMS is intentionally shorter — carriers split long messages and
# each segment costs money.
SMS_BODIES = {
    "email": "OMA Flowers verification code: {code}. Valid {mins} min. Do not share.",
    "password_reset": "OMA Flowers password reset code: {code}. Valid {mins} min. Do not share.",
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

def _render_email_body(code_type: str, code: str, is_resend: bool) -> str:
    cfg = EMAIL_TYPES.get(code_type, EMAIL_TYPES["email"])
    intro = cfg["resend_intro"] if is_resend else cfg["intro"]
    return (
        f"{intro}\n\n"
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
    body = _render_email_body(code_type, code, is_resend)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(
            "Verification email (%s) sent to %s", code_type, user.email
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to send verification email (%s) to %s: %s",
            code_type,
            user.email,
            exc,
        )
        return False


# ------------------------------------------------------------------
# SMS rendering + send
# ------------------------------------------------------------------

def _render_sms_body(code_type: str, code: str) -> str:
    template = SMS_BODIES.get(code_type, SMS_BODIES["email"])
    return template.format(code=code, mins=CODE_TTL_MINUTES)


def send_verification_sms(
    user: User,
    code: str,
    code_type: str = "email",
) -> bool:
    """
    Send the verification code via Africa's Talking SMS.

    Uses the phone number stored on the user (`phone` or, for
    distributors, `user.mobile_number` if you have one). Returns
    False if the user has no phone on file or if AT rejects it.
    """
    phone = (
        getattr(user, "phone", None)
        or getattr(user, "mobile_number", None)
    )
    if not phone:
        logger.info(
            "send_verification_sms: user %s has no phone, skipping",
            user.pk,
        )
        return False

    message = _render_sms_body(code_type, code)
    sent = send_sms(phone, message)
    if sent:
        logger.info(
            "Verification SMS (%s) sent to %s", code_type, phone
        )
    return sent


# ------------------------------------------------------------------
# High-level helpers — send BOTH channels, return both results
# ------------------------------------------------------------------

def issue_verification_code(
    user: User,
) -> Tuple[VerificationCode, bool, bool]:
    """
    Email-verification flow:
      1. Invalidate old codes of this type
      2. Create a fresh 6-digit code
      3. Send email + SMS in parallel

    Returns (verification, email_sent, sms_sent).
    """
    verification = create_verification_code(user, code_type="email")
    email_sent = send_verification_email(user, verification.code, "email")
    sms_sent = send_verification_sms(user, verification.code, "email")

    if not email_sent and not sms_sent:
        logger.error(
            "Verification code delivered on NO channel for user %s",
            user.pk,
        )
    return verification, email_sent, sms_sent


def issue_password_reset_code(
    user: User,
) -> Tuple[VerificationCode, bool, bool]:
    """
    Password-reset flow: same as `issue_verification_code` but with
    the password_reset code type.
    """
    verification = create_verification_code(
        user, code_type="password_reset"
    )
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
    """
    Same as `issue_verification_code` but sends the "resend" email
    variant (different subject/intro). Old codes are invalidated.
    """
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
# Verification helper (used by verify endpoints)
# ------------------------------------------------------------------

def verify_code(
    user: User,
    code: str,
    code_type: str = "email",
) -> Tuple[bool, str]:
    """
    Look up and validate a submitted code.

    Returns (ok, reason):
      - (True,  "")              → valid, has been consumed
      - (False, "invalid_code")  → not found / already used
      - (False, "expired")       → exists but past its TTL
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
            code_type,
            user.email,
            code,
        )
        return False, "invalid_code"

    if not verification.is_valid():
        logger.warning(
            "Expired %s code for %s (expired_at=%s)",
            code_type,
            user.email,
            verification.expires_at,
        )
        return False, "expired"

    verification.is_used = True
    verification.save(update_fields=["is_used"])
    return True, ""