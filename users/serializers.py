# auth/serializers.py
import base64
import binascii

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


# ---------------------------------------------------------------------------
# Fields shared by every serializer (must match `User` in src/types/index.ts)
# ---------------------------------------------------------------------------
USER_SCALAR_FIELDS = (
    'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
    'phone', 'country', 'region', 'city',
    'user_type', 'status', 'email_verified', 'email_verified_at',
    'created_at', 'updated_at',
    'last_login', 'date_joined',
    'is_active', 'is_staff', 'is_superuser',
)

USER_READ_ONLY = (
    'id', 'email_verified', 'created_at', 'updated_at',
    'user_type', 'status',
    'last_login', 'date_joined',
    'is_active', 'is_staff', 'is_superuser',
)

# 5 MB of base64 ≈ 3.75 MB original — generous but bounded.
MAX_PROFILE_PICTURE_B64_LEN = 5 * 1024 * 1024


def _full_name(obj) -> str:
    return (obj.full_name or f"{obj.first_name or ''} {obj.last_name or ''}").strip()


# ---------------------------------------------------------------------------
# Full user (profile page — INCLUDES base64 profile_picture)
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = USER_SCALAR_FIELDS + ('profile_picture',)
        read_only_fields = USER_READ_ONLY + ('profile_picture',)

    def get_full_name(self, obj):
        return _full_name(obj)


# ---------------------------------------------------------------------------
# Login user (lean — NO base64, just a boolean flag)
# ---------------------------------------------------------------------------
class LoginUserSerializer(serializers.ModelSerializer):
    """
    What /auth/login/ returns. Type-complete for `User` in
    src/types/index.ts, plus a tiny `has_profile_picture` hint.
    Never returns the base64 blob.
    """
    full_name = serializers.SerializerMethodField()
    has_profile_picture = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        # `profile_picture` is included in the field list only so the JSON
        # shape matches `User` — but the getter returns None, never base64.
        fields = USER_SCALAR_FIELDS + ('profile_picture', 'has_profile_picture')
        read_only_fields = fields

    def get_full_name(self, obj):
        return _full_name(obj)

    def get_has_profile_picture(self, obj):
        return bool(obj.profile_picture)

    def get_profile_picture(self, obj):
        # ✅ Deliberately empty — login must never ship base64.
        return None


# ---------------------------------------------------------------------------
# Register — unchanged except profile size validation
# ---------------------------------------------------------------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            'email', 'username', 'first_name', 'last_name', 'phone',
            'country', 'region', 'city', 'profile_picture',
            'password', 'password2',
        )

    def validate_profile_picture(self, value):
        return _validate_base64_picture(value)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {'password2': "Password fields didn't match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        user.user_type = 'customer'
        user.status = 'pending'
        user.save(update_fields=['user_type', 'status'])
        return user


# ---------------------------------------------------------------------------
# Login — unchanged
# ---------------------------------------------------------------------------
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(email=email, password=password)
        if user is None:
            user = authenticate(username=email, password=password)

        if user is None:
            existing = User.objects.filter(email__iexact=email).first()
            if existing and existing.status == 'banned':
                raise serializers.ValidationError(
                    {'error': 'Your account has been banned.'}
                )
            if existing and not existing.is_active:
                raise serializers.ValidationError(
                    {'error': 'This account is inactive. Please contact support.'}
                )
            raise serializers.ValidationError(
                {'error': 'Invalid email or password.'}
            )

        if user.status == 'banned':
            raise serializers.ValidationError(
                {'error': 'Your account has been banned.'}
            )

        attrs['user'] = user
        return attrs


# ---------------------------------------------------------------------------
# Change password — unchanged
# ---------------------------------------------------------------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True, write_only=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': "Passwords don't match."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Email verification / password reset — unchanged
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
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': "Passwords don't match."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Profile update — accepts base64 but with a hard size cap
# ---------------------------------------------------------------------------
class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'first_name', 'last_name', 'phone', 'country', 'region',
            'city', 'profile_picture',
        )

    def validate_profile_picture(self, value):
        return _validate_base64_picture(value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_base64_picture(value):
    """
    Accept either:
      * None / ''                → clear the picture
      * 'data:image/...;base64,…' → base64 data URI
    Reject anything else, or anything larger than MAX_PROFILE_PICTURE_B64_LEN.
    """
    if value in (None, ''):
        return value

    if not isinstance(value, str):
        raise serializers.ValidationError('profile_picture must be a string.')

    if len(value) > MAX_PROFILE_PICTURE_B64_LEN:
        mb = MAX_PROFILE_PICTURE_B64_LEN / (1024 * 1024)
        raise serializers.ValidationError(
            f'Profile picture is too large (max {mb:.0f} MB after base64 encoding). '
            'Please upload a smaller image.'
        )

    if not value.startswith('data:image/'):
        raise serializers.ValidationError(
            'profile_picture must be a data URI of the form '
            '"data:image/<type>;base64,<data>".'
        )

    # Validate it actually decodes (cheap sanity check on the header).
    try:
        header, b64 = value.split(',', 1)
    except ValueError:
        raise serializers.ValidationError('Malformed data URI.')

    if ';base64' not in header:
        raise serializers.ValidationError(
            'profile_picture data URI must use base64 encoding.'
        )

    try:
        base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise serializers.ValidationError('profile_picture is not valid base64.')

    return value