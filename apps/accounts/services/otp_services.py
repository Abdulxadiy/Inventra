import secrets
import redis
from django.conf import settings

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

OTP_TTL_SECONDS = 300 # 5 minute
MAX_ATTEMPTS = 5

def _otp_key(phone_number: str) -> str:
    return f"otp:{phone_number}"

def _attempts_key(phone_number: str) -> str:
    return f"otp_attempts:{phone_number}"

def generate_code() -> str:
    return ''.join(
        secrets.choice('0123456789')
        for _ in range(6)
    )

def store_code(phone_number: str, code: str) -> None:
    redis_client.setex(_otp_key(phone_number), OTP_TTL_SECONDS, code)
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
