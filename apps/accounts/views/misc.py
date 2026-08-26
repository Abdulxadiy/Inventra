from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.services import otp_services
from apps.tg_bot.models import TelegramContact
from apps.tg_bot.services import send_telegram_message


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }

def get_telegram_contact_or_error(phone_number):
    """
    Common for both flows (register/login): telegram_not_linked
    Removed because the check and cooldown check are the same.
    """
    try:
        contact = TelegramContact.objects.get(phone_number=phone_number)
    except TelegramContact.DoesNotExist:
        return None, Response(
            {'error': 'telegram_contact_not_found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if otp_services.is_in_cooldown(phone_number):
        return None, Response(
            {'error': 'cooldown'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return contact, None

def send_otp_or_error(phone_number, contact):
    code = otp_services.generate_code()
    otp_services.store_code(phone_number, code)

    sent = send_telegram_message(
        contact.chat_id,
        f"Sizning tasdiqlash kodingiz: {code}\nKod faqat 5 daqiqa amal qiladi!",
    )
    if not sent:
        otp_services.discard_code(phone_number)
        return Response(
            {'error': 'telegram_send_failed'},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return None