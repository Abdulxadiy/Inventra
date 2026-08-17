from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from rest_framework import status

from .serializers import RequestOTPSerializer, VerifyOTPSerializer
from .services import otp_services
from apps.tg_bot.models import TelegramContact
from apps.tg_bot.services import send_telegram_message

User = get_user_model()


class RequestOTPView(APIView):
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']

        if not User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            contact = TelegramContact.objects.get(phone_number=phone_number)
        except TelegramContact.DoesNotExist:
            return Response(
                {'error': 'Telegram not linked'},
                status=status.HTTP_400_BAD_REQUEST
            )

        code = otp_services.generate_code()
        otp_services.store_code(phone_number, code)

        sent = send_telegram_message(
            contact.chat_id,
            f"Sizning tasdiqlash kodingiz {code}\nKod faqat 5 daqiqa amal qiladi!"
        )

        if not sent:
            return Response(
                {'error': 'Telegram send failed'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        return Response(status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']

        is_valid, error_reason = otp_services.verify_code(phone_number, code)

        if not is_valid:
            return Response(
                {'error': error_reason},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.get(phone_number=phone_number)
        refresh = RefreshToken.for_user(user)

        return Response(
            {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            },    
            status=status.HTTP_200_OK)
