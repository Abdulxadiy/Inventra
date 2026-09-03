"""
Admin-panel login for staff / owner / platform_admin: username+ password,
then a Telegram OTP as a second factor. Separate from the customer
phone-OTP login in login.py -- different audience, different
security requirements.
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.services import login_throttle, otp_services
from apps.accounts.services.phone_utils import mask_phone_number
from api.v1.accounts.serializers import AdminLoginSerializer, AdminLoginVerifyOTPSerializer
from api.v1.accounts.views.misc import (
    get_telegram_contact_or_error,
    send_otp_or_error,
    issue_tokens
)

User = get_user_model()


def _bad_credentials():
    return Response(
        {"detail": "Username or password incorrect!"},
        status=status.HTTP_401_UNAUTHORIZED,

    )


def _bad_otp():
    return Response(
        {"detail": "Verification code incorrect!"},
        status=status.HTTP_401_UNAUTHORIZED,
    )


def _blocked(second_remining: int):
    return Response(
        {
            "detail": (
                "Too many failed attempts from this device. Access to"
                "this platform has been blocked. Contact the"
                "administrator to restore access."
            ),
            "retry_after_seconds": second_remining,
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


class AdminLoginView(APIView):
    """POST /api/v1/accounts/auth/admin-login/ {username, password}"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        locked, remining =login_throttle.is_locked(username)
        if locked:
            return _blocked(remining)
        user = User.objects.filter(username=username).first()

        if user is None or not user.check_password(password):
            login_throttle.register_failure(username)
            return _bad_credentials()

        if user.role not in ("staff", "owner", "platform_admin"):
            # Shouldn't happen structurally (customers never get a
            # username), but stay defensive rather than silently allow it.
            login_throttle.register_failure(username)
            return _bad_credentials()

        if not user.is_active:
            locked, remining = login_throttle.is_locked(username)
            return _blocked(remining if locked else 0)

        contact, error = get_telegram_contact_or_error(user.phone_number)
        if error:
            if error.status_code == status.HTTP_404_NOT_FOUND:
                # Don't reval "telegram not linked" specifically
                return Response(
                    {"detail": "Verification code couldn't be sent."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return error

        error = send_otp_or_error(user.phone_number, contact)
        if error:
            return error

        return Response(
            {
                "detail": "Verification code sent.",
                "phone_hint": mask_phone_number(user.phone_number),
            },
            status=status.HTTP_200_OK,
        )


class AdminLoginVerifyOTPView(APIView):
    """POST /api/v1/accounts/auth/admin-login/verify-otp/ {username, verification_code}"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        code = serializer.validated_data['verification_code']

        locked, remining = login_throttle.is_locked(username)
        if locked:
            return _blocked(remining)

        user = User.objects.filter(username=username).first()
        if user is None:
            login_throttle.register_failure(username)
            return _bad_otp()

        is_valid, _reason = otp_services.verify_code(user.phone_number, code)
        if not is_valid:
            login_throttle.register_failure(username)
            return _bad_otp()

        if not user.is_active:
            locked, remining = login_throttle.is_locked(username)
            return _blocked(remining if locked else 0)

        login_throttle.register_success(username)
        return Response(issue_tokens(user), status=status.HTTP_200_OK)
