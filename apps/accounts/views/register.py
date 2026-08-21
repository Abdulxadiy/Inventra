from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.models import User
from apps.accounts.serializers import PhoneNumberSerializer, VerifyOTPSerializer
from apps.accounts.services import otp_services
from apps.accounts.views.misc import get_telegram_contact_or_error, send_otp_or_error, issue_tokens


class RegisterRequestOTPView(APIView):
    def post(self, request):
        serializer = PhoneNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']

        if User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {'error': 'user_already_exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        contact, error_reason = get_telegram_contact_or_error(phone_number)
        if error_reason:
            return error_reason

        error_reason = send_otp_or_error(phone_number, contact)
        if error_reason:
            return error_reason

        return Response(status=status.HTTP_200_OK)


class RegisterVerifyOTPView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['verification_code']

        if User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {'error': 'user_already_exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_valid, error_reasons = otp_services.verify_code(phone_number, code)
        if not is_valid:
            return Response({'error': error_reasons}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            phone_number=phone_number,
            role='customer',
            is_phone_verified=True,
        )

        user.set_unusable_password()
        user.save()

        tokens = issue_tokens(user)
        return Response({
            **tokens,
            'needs_profile_completion': not user.profile_completed,
        }, status=status.HTTP_201_CREATED)
