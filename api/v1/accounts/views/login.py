from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from api.v1.accounts.serializers import PhoneNumberSerializer, VerifyOTPSerializer
from rest_framework.views import APIView
from apps.accounts.services import otp_services
from api.v1.accounts.views.misc import get_telegram_contact_or_error, send_otp_or_error, issue_tokens

User = get_user_model()


class LoginRequestOTPView(APIView):
    def post(self, request):
        serializer = PhoneNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']

        if not User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {'error': 'user_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )

        contact, error_reason = get_telegram_contact_or_error(phone_number)

        if error_reason:
            return error_reason

        error_reason = send_otp_or_error(phone_number, contact)
        if error_reason:
            return error_reason

        return Response(status=status.HTTP_200_OK)


class LoginVerifyOTPView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['verification_code']

        is_valid, error_reason = otp_services.verify_code(phone_number, code)
        if not is_valid:
            return Response({'error': error_reason}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({'error': 'user_not_found'}, status=status.HTTP_404_NOT_FOUND)

        tokens = issue_tokens(user)
        return Response({
            **tokens,
            'needs_profile_completion': not user.profile_completed,
        }, status=status.HTTP_200_OK)
