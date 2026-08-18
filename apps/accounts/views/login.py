from rest_framework import status
from rest_framework.response import Response
from apps.accounts.models import User
from apps.accounts.serializers import PhoneNumberSerializer
from rest_framework.views import APIView
from apps.accounts.views.misc import get_telegram_contact_or_error, send_otp_or_error


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

        contact, error_response = get_telegram_contact_or_error(phone_number)

        if error_response:
            return error_response

        error_response = send_otp_or_error(phone_number, contact)
        if error_response:
            return error_response

        return Response(status=status.HTTP_200_OK)