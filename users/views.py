# auth/views.py
"""
Authentication views for OMA Flowers.

Verification-code flows delegate to `auth.utils`. Login accepts a
single `identifier` (OMA User ID | email | username) + password;
legacy `{ email, password }` payloads still work.
"""

import logging

from django.contrib.auth import authenticate  # noqa: F401
from django.utils import timezone
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    LoginUserSerializer,
    ChangePasswordSerializer,
    EmailVerificationSerializer,
    ResetPasswordRequestSerializer,
    ResetPasswordVerifySerializer,
    UpdateProfileSerializer,
)
from .utils import (
    issue_verification_code,
    issue_password_reset_code,
    resend_verification_code,
    verify_code,
)

logger = logging.getLogger(__name__)


# ==================================================================
# REGISTRATION
# ==================================================================

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # user.user_id is set on first save() — send it in the email
        # and SMS alongside the verification code.
        _, email_sent, sms_sent = issue_verification_code(user)

        if not email_sent and not sms_sent:
            logger.warning(
                "Verification code could not be delivered to %s on email "
                "or SMS — user can request a new one.", user.email,
            )

        if email_sent and sms_sent:
            message = (
                "Registration successful. Your OMA User ID and a "
                "verification code have been sent to your email and phone."
            )
        elif email_sent:
            message = (
                "Registration successful. Your OMA User ID and a "
                "verification code have been sent to your email."
            )
        elif sms_sent:
            message = (
                "Registration successful. Your OMA User ID and a "
                "verification code have been sent to your phone."
            )
        else:
            message = (
                "Registration successful, but we could not send your OMA "
                "User ID or verification code. Please use 'Resend "
                "verification' in a moment."
            )

        return Response(
            {
                "message": message,
                "email": user.email,
                "user_id": user.user_id,
            },
            status=status.HTTP_201_CREATED,
        )


# ==================================================================
# LOGIN / LOGOUT / TOKENS
# ==================================================================

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        distributor_data = None
        if user.user_type == "distributor":
            try:
                d = user.distributor_profile
                distributor_data = {
                    "id": d.id,
                    "rank": d.rank,
                    "level": d.level,
                    "pbv": str(d.pbv),
                    "cgv": str(d.cgv),
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Distributor profile unavailable for %s: %s",
                    user.email, exc,
                )

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": LoginUserSerializer(
                    user, context={"request": request}
                ).data,
                "distributor": distributor_data,
                "user_type": user.user_type,
            },
            status=status.HTTP_200_OK,
        )


class RefreshTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            return Response({"access": str(refresh.access_token)})
        except Exception as exc:  # noqa: BLE001
            logger.info("Invalid refresh token: %s", exc)
            return Response(
                {"error": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
        except Exception as exc:  # noqa: BLE001
            logger.info("Logout blacklist failed: %s", exc)
        return Response({"message": "Logged out successfully"})


# ==================================================================
# PROFILE
# ==================================================================

class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UpdateProfileView(generics.UpdateAPIView):
    serializer_class = UpdateProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Wrong password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"message": "Password changed successfully"})


# ==================================================================
# EMAIL VERIFICATION
# ==================================================================

class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logger.info("Verify email: unknown user %s", email)
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.email_verified:
            return Response(
                {"message": "Email already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ok, reason = verify_code(user, code, code_type="email")
        if not ok:
            if reason == "expired":
                return Response(
                    {
                        "error": (
                            "Verification code has expired. "
                            "Please request a new one."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"error": "Invalid verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.status = "active"
        user.save(
            update_fields=["email_verified", "email_verified_at", "status"]
        )

        logger.info("Email verified: %s", email)
        return Response({"message": "Email verified successfully"})


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.email_verified:
            return Response(
                {"message": "Email already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _, email_sent, sms_sent = resend_verification_code(user)

        if not email_sent and not sms_sent:
            return Response(
                {
                    "message": (
                        "Unable to send the verification code right now. "
                        "Please try again in a moment."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if email_sent and sms_sent:
            message = "New verification code sent to your email and phone."
        elif email_sent:
            message = "New verification code sent to your email."
        else:
            message = "New verification code sent to your phone."

        return Response({"message": message})


# ==================================================================
# PASSWORD RESET
# ==================================================================

class ResetPasswordRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logger.info("Password reset: unknown user %s", email)
            return Response(
                {
                    "message": (
                        "If that email is registered, a reset code "
                        "has been sent."
                    )
                }
            )

        _, email_sent, sms_sent = issue_password_reset_code(user)
        if not email_sent and not sms_sent:
            logger.error(
                "Password reset code failed to send on BOTH channels for %s",
                email,
            )

        return Response(
            {
                "message": (
                    "If that email is registered, a reset code has been sent."
                )
            }
        )


class ResetPasswordVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        password = serializer.validated_data["password"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        ok, reason = verify_code(user, code, code_type="password_reset")
        if not ok:
            if reason == "expired":
                return Response(
                    {
                        "error": (
                            "Verification code has expired. "
                            "Please request a new one."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"error": "Invalid verification code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=["password"])

        logger.info("Password reset completed for %s", email)
        return Response({"message": "Password reset successfully"})


# ==================================================================
# ADMIN / USER LIST
# ==================================================================

class AdminUsersListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = User.objects.all().order_by("-created_at")

        user_type = self.request.query_params.get("user_type")
        if user_type:
            queryset = queryset.filter(user_type=user_type)

        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        exclude_distributors = self.request.query_params.get(
            "exclude_distributors", "true"
        )
        if exclude_distributors == "true":
            queryset = queryset.exclude(user_type="distributor")

        return queryset.exclude(user_type="admin")


class CustomerListView(generics.ListAPIView):
    queryset = User.objects.filter(user_type="customer").order_by(
        "-created_at"
    )
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ["email", "first_name", "last_name", "user_id"]