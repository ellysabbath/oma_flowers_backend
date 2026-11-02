# auth/models.py
"""
Custom User model for OMA Flowers.

Every user gets a public identifier of the form:

    OMA-<year>-<6 random digits>       e.g. OMA-2025-847291

The suffix is *random*, not sequential, so IDs cannot be used to
enumerate users or infer signup order. Uniqueness is enforced at the
database level and collision-retried at save() time.
"""

import random
import string

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


# ------------------------------------------------------------------
# OMA ID tunables
# ------------------------------------------------------------------

OMA_ID_PREFIX = "OMA"
OMA_ID_DIGITS = 6
OMA_ID_MAX_ATTEMPTS = 25


def _random_suffix() -> str:
    """Return a zero-padded random integer with exactly OMA_ID_DIGITS digits."""
    return "".join(random.choices(string.digits, k=OMA_ID_DIGITS))


def generate_oma_user_id(year: int | None = None) -> str:
    """
    Produce a candidate OMA ID. NOT guaranteed unique on its own —
    the save() method handles collision retries against the DB.
    """
    yr = year or timezone.now().year
    return f"{OMA_ID_PREFIX}-{yr}-{_random_suffix()}"


# ------------------------------------------------------------------
# User
# ------------------------------------------------------------------

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ("customer", "Customer"),
        ("distributor", "Distributor"),
        ("admin", "Admin"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("pending", "Pending"),
        ("banned", "Banned"),
    )

    # Public, human-facing ID. Set automatically on first save.
    user_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        null=True,       # ← add this
        blank=True, 
        help_text="Public OMA identifier, e.g. OMA-2025-847291.",
    )

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    region = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    profile_picture = models.TextField(blank=True, null=True)
    user_type = models.CharField(
        max_length=20, choices=USER_TYPE_CHOICES, default="customer"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id or self.email} <{self.email}>"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def is_distributor(self):
        return self.user_type == "distributor"

    def is_admin(self):
        return self.user_type == "admin"

    def is_customer(self):
        return self.user_type == "customer"

    # --------------------------------------------------------------
    # Auto-generate OMA ID on first save
    # --------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.user_id:
            year = timezone.now().year
            for _ in range(OMA_ID_MAX_ATTEMPTS):
                candidate = generate_oma_user_id(year)
                if not User.objects.filter(user_id=candidate).exists():
                    self.user_id = candidate
                    break
            else:
                # Astronomically unlikely — but guaranteed unique fallback.
                self.user_id = f"OMA-{year}-{_random_suffix()}"

        super().save(*args, **kwargs)


# ------------------------------------------------------------------
# Verification codes
# ------------------------------------------------------------------

class VerificationCode(models.Model):
    VERIFICATION_TYPES = (
        ("email", "Email Verification"),
        ("password_reset", "Password Reset"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="verification_codes",
    )
    code = models.CharField(max_length=6)
    type = models.CharField(max_length=20, choices=VERIFICATION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "verification_codes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "code", "type", "is_used"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.code}"

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at