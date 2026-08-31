import secrets
import redis
from django.conf import settings

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

OTP_TTL_SECONDS = 300  # The code is valid for only 5 minutes
MAX_ATTEMPTS = 5       # Number of incorrect attempts
COOLDOWN_SECONDS = 60  # Waiting time to request an OTP again to a number


def _otp_key(phone_number: str) -> str:
    return f"otp:{phone_number}"

def _attempts_key(phone_number: str) -> str:
    return f"otp_attempts:{phone_number}"

def _cooldown_key(phone_number: str) -> str:
    return f"cooldown:{phone_number}"

def generate_code() -> str:
    return ''.join(
        secrets.choice('0123456789')
        for _ in range(6)
    )

def is_in_cooldown(phone_number: str) -> bool:
    return redis_client.exists(_cooldown_key(phone_number)) == 1

def store_code(phone_number: str, code: str) -> None:
    redis_client.set(_otp_key(phone_number), code, ex=OTP_TTL_SECONDS)
    redis_client.set(_cooldown_key(phone_number), '1', ex=COOLDOWN_SECONDS)
    redis_client.delete(_attempts_key(phone_number))

def discard_code(phone_number: str) -> None:
    """
    If sanding to Telegram fails we cancel the saved code and cooldown,
    otherwise the user will wait for a code that he never sent.
    """
    redis_client.delete(_otp_key(phone_number))
    redis_client.delete(_cooldown_key(phone_number))
    redis_client.delete(_attempts_key(phone_number))

def verify_code(phone_number: str, code: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_reason)
    Error reason: 'expired' | 'too_many_attempts' | 'invalid_code' | ''
    """
    attempts_key = _attempts_key(phone_number)
    attempts = redis_client.incr(attempts_key)
    redis_client.expire(attempts_key, OTP_TTL_SECONDS)

    if attempts > MAX_ATTEMPTS:
        return False, 'Too many attempts'

    stored_code = redis_client.get(_otp_key(phone_number))
    if stored_code is None:
        return False, 'Expired'

    if stored_code != code:
        return False, 'Invalid code'

    # We should delete the code after verify because one code for only one time
    redis_client.delete(_otp_key(phone_number))
    redis_client.delete(attempts_key)
    return True, ''
