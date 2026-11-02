# auth/serializers.py
"""
Serializers for OMA Flowers auth.

Login now accepts a single `identifier` (OMA User ID | email | username)
alongside `password`. Legacy `{ email, password }` payloads still work.
"""

import base64
import binascii

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from rest_framework import serializers

from .models import User

# ---------------------------------------------------------------------------
# Field lists shared by every serializer (must match src/types/index.ts)
# ---------------------------------------------------------------------------
USER_SCALAR_FIELDS = (
    "id", "user_id",
    "email", "username", "first_name", "last_name", "full_name",
    "phone", "country", "region", "city",
    "user_type", "status", "email_verified", "email_verified_at",
    "created_at", "updated_at",
    "last_login", "date_joined",
    "is_active", "is_staff", "is_superuser",
)

USER_READ_ONLY = (
    "id", "user_id",
    "email_verified", "created_at", "updated_at",
    "user_type", "status",
    "last_login", "date_joined",
    "is_active", "is_staff", "is_superuser",
)

MAX_PROFILE_PICTURE_B64_LEN = 5 * 1024 * 1024  # 5 MB


def _full_name(obj) -> str:
    return (
        obj.full_name or f"{obj.first_name or ''} {obj.last_name or ''}"
    ).strip()


# ---------------------------------------------------------------------------
# Full user (profile page — INCLUDES base64 profile_picture)
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = USER_SCALAR_FIELDS + ("profile_picture",)
        read_only_fields = USER_READ_ONLY + ("profile_picture",)

    def get_full_name(self, obj):
        return _full_name(obj)


# ---------------------------------------------------------------------------
# Login user (lean — NO base64, just a boolean flag)
# ---------------------------------------------------------------------------
class LoginUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    has_profile_picture = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = USER_SCALAR_FIELDS + ("profile_picture", "has_profile_picture")
        read_only_fields = fields

    def get_full_name(self, obj):
        return _full_name(obj)

    def get_has_profile_picture(self, obj):
        return bool(obj.profile_picture)

    def get_profile_picture(self, obj):
        return None  # login must never ship base64


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            "email", "username", "first_name", "last_name", "phone",
            "country", "region", "city", "profile_picture",
            "password", "password2",
        )

    def validate_profile_picture(self, value):
        return _validate_base64_picture(value)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "Password fields didn't match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        user.user_type = "customer"
        user.status = "pending"
        user.save(update_fields=["user_type", "status"])
        return user


# ---------------------------------------------------------------------------
# Login — identifier (user_id | email | username) + password
# ---------------------------------------------------------------------------
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = (
            attrs.get("identifier") or attrs.get("email") or ""
        ).strip()
        password = attrs.get("password")

        if not identifier:
            raise serializers.ValidationError(
                {"identifier": "User ID, email, or username is required."}
            )

        # Look up the candidate — but do NOT leak whether they exist.
        candidate = (
            User.objects.filter(
                Q(user_id__iexact=identifier)
                | Q(email__iexact=identifier)
                | Q(username__iexact=identifier)
            ).first()
        )

        # Authenticate against the resolved email (USERNAME_FIELD).
        authed = None
        if candidate:
            authed = authenticate(email=candidate.email, password=password)

        # Legacy fallbacks (raw identifier used as email/username)
        if authed is None:
            authed = authenticate(username=identifier, password=password)
        if authed is None:
            authed = authenticate(email=identifier, password=password)

        if authed is None:
            if candidate and candidate.status == "banned":
                raise serializers.ValidationError(
                    {"error": "Your account has been banned."}
                )
            if candidate and not candidate.is_active:
                raise serializers.ValidationError(
                    {
                        "error": "This account is inactive. "
                        "Please contact support."
                    }
                )
            raise serializers.ValidationError(
                {"error": "Invalid credentials."}
            )

        if authed.status == "banned":
            raise serializers.ValidationError(
                {"error": "Your account has been banned."}
            )

        attrs["user"] = authed
        return attrs


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True, write_only=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords don't match."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Verification / reset
# ---------------------------------------------------------------------------
class EmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(max_length=6, required=True)


class ResetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class ResetPasswordVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(max_length=6, required=True)
    password = serializers.CharField(
        required=True, write_only=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords don't match."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Profile update
# ---------------------------------------------------------------------------
class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "first_name", "last_name", "phone", "country", "region",
            "city", "profile_picture",
        )

    def validate_profile_picture(self, value):
        return _validate_base64_picture(value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_base64_picture(value):
    if value in (None, ""):
        return value

    if not isinstance(value, str):
        raise serializers.ValidationError("profile_picture must be a string.")

    if len(value) > MAX_PROFILE_PICTURE_B64_LEN:
        mb = MAX_PROFILE_PICTURE_B64_LEN / (1024 * 1024)
        raise serializers.ValidationError(
            f"Profile picture is too large (max {mb:.0f} MB after base64 "
            "encoding). Please upload a smaller image."
        )

    if not value.startswith("data:image/"):
        raise serializers.ValidationError(
            'profile_picture must be a data URI of the form '
            '"data:image/<type>;base64,<data>".'
        )

    try:
        header, b64 = value.split(",", 1)
    except ValueError:
        raise serializers.ValidationError("Malformed data URI.")

    if ";base64" not in header:
        raise serializers.ValidationError(
            "profile_picture data URI must use base64 encoding."
        )

    try:
        base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise serializers.ValidationError(
            "profile_picture is not valid base64."
        )

    return value