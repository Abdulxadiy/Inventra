import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_message(chat_id: str, text: str) -> bool:
    try:
        response = requests.post(
            TELEGRAM_API_URL,
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=5,
        )
        response.raise_for_status()

        data = response.json()
        if not data.get("ok"):
            logger.error(f"Telegram API error: %s", data)
            return False
        return True
    except Exception as e:
        logger.error(f"Telegram send failed for chat_id: {chat_id} | error: {e}")
        return False
