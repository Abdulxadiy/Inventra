from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from api.v1.accounts.serializers import PhoneNumberSerializer, VerifyOTPSerializer
from rest_framework.views import APIView
from apps.accounts.services import otp_services, customer_login_throttle
from api.v1.accounts.views.misc import get_telegram_contact_or_error, send_otp_or_error, issue_tokens

User = get_user_model()


def _blocked(seconds_remaining: int):
    return Response(
        {
            "detail": (
                "Too many attempts from this device. Access has been "
                "temporarily blocked. Contact the administrator to "
                "restore access."
            ),
            "retry_after_seconds": seconds_remaining,
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


class LoginRequestOTPView(APIView):
    def post(self, request):
        serializer = PhoneNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']

        locked, remaining = customer_login_throttle.is_locked(phone_number)
        if locked:
            return _blocked(remaining)

        user = User.objects.filter(phone_number=phone_number).first()
        if user is None:
            return Response(
                {'error': 'user_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.is_active:
            # Already banned (3-strike, or manually deactivated) --
            # don't waste an OTP send, and don't let this reset/advance
            # throttle state on top of an existing ban.
            locked, remaining = customer_login_throttle.is_locked(phone_number)
            return _blocked(remaining if locked else 0)

        contact, error_reason = get_telegram_contact_or_error(phone_number)
        if error_reason:
            return error_reason

        error_reason = send_otp_or_error(phone_number, contact)
        if error_reason:
            return error_reason

        # Every OTP actually sent counts as one attempt, on top of wrong
        # verifications below -- guards against OTP-request spam, not
        # just code-guessing (see customer_login_throttle module docstring).
        customer_login_throttle.register_attempt(phone_number)
        return Response(status=status.HTTP_200_OK)


class LoginVerifyOTPView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['verification_code']

        locked, remaining = customer_login_throttle.is_locked(phone_number)
        if locked:
            return _blocked(remaining)

        is_valid, error_reason = otp_services.verify_code(phone_number, code)
        if not is_valid:
            customer_login_throttle.register_attempt(phone_number)
            return Response({'error': error_reason}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            customer_login_throttle.register_attempt(phone_number)
            return Response({'error': 'user_not_found'}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            locked, remaining = customer_login_throttle.is_locked(phone_number)
            return _blocked(remaining if locked else 0)

        customer_login_throttle.register_success(phone_number)
        tokens = issue_tokens(user)
        return Response({
            **tokens,
            'needs_profile_completion': not user.profile_completed,
        }, status=status.HTTP_200_OK)