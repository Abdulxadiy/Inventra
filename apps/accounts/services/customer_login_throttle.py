"""
Progressive login-attempt throttling + permanent ban for the customer
phone-OTP login flow (see login.py). Parallel to
apps/accounts/services/login_throttle.py (the admin-panel version) but
keyed by phone_number instead of username, and deliberately kept as a
SEPARATE module rather than a shared/parametrized one -- the two flows
protect different attack surfaces (password+OTP vs. phone-OTP-only)
and are free to diverge independently later.

Design (same stage/ban shape as the admin version, by design):
- One shared attempt counter per phone_number covers BOTH:
    - requesting a new login OTP (guards against OTP-spam / Telegram
      delivery-cost abuse), and
    - submitting a wrong/expired OTP code (guards against code
      guessing)
  -- either counts as one attempt toward the same counter.
- Attempts escalate through three stages:
    stage 0: 5 attempts -> 60 second lock
    stage 1: 3 attempts -> 1 hour lock
    stage 2: 1 attempt  -> 1 day lock, and this counts as one "strike"
             toward a permanent ban
- After a stage-2 (1 day) lock expires, the cycle restarts at stage 0.
- A successful login clears everything, including the ban-strike
  streak -- a customer who eventually logs in successfully is never
  at risk regardless of how many past login cycles they've done.
- 3 strikes -> User.is_active = False (permanent ban). Only a
  platform_admin can lift this, via your unban endpoint -- it should
  work for this too, since it looks the target up by user id/phone,
  not by username.
"""
import redis
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# (max_attempts, lock_seconds) per stage, in escalation order
_STAGES = [
    (5, 60),    # stage 0: 5 attempts -> 60 second lock
    (3, 3600),  # stage 1: 3 attempts -> 1 hour lock
    (1, 86400), # stage 2: 1 attempt -> 1 day lock
]
_FINAL_STAGE = len(_STAGES) - 1

_BAN_STRIKE_LIMIT = 3
_STRIKE_COUNTER_TTL = 60 * 60 * 24 * 7  # 7 days: must outlive the 1-day locks


def _stage_key(phone_number: str) -> str:
    return f"customer_login:stage:{phone_number}"

def _attempts_key(phone_number: str) -> str:
    return f"customer_login:attempts:{phone_number}"

def _lock_key(phone_number: str) -> str:
    return f"customer_login:locked:{phone_number}"

def _strikes_key(phone_number: str) -> str:
    return f"customer_login:strikes:{phone_number}"


def is_locked(phone_number: str) -> tuple[bool, int]:
    """Returns (locked, seconds_remaining). Call before sending a new
    OTP AND before checking a submitted OTP."""
    ttl = redis_client.ttl(_lock_key(phone_number))
    if ttl and ttl > 0:
        return True, ttl
    return False, 0


def register_attempt(phone_number: str) -> None:
    """Call after EITHER: a new OTP was just sent, or a submitted OTP
    code turned out to be wrong/expired. (Named `attempt`, not
    `failure`, since a successfully-sent OTP still counts here --
    unlike login_throttle.register_failure, which only fires on
    genuine failures.)"""
    stage = int(redis_client.get(_stage_key(phone_number)) or 0)
    stage = min(stage, _FINAL_STAGE)
    max_attempts, lock_seconds = _STAGES[stage]

    attempts = redis_client.incr(_attempts_key(phone_number))
    if attempts == 1:
        redis_client.expire(_attempts_key(phone_number), lock_seconds + 60)

    if attempts < max_attempts:
        return

    redis_client.set(_lock_key(phone_number), "1", ex=lock_seconds)
    redis_client.delete(_attempts_key(phone_number))

    if stage == _FINAL_STAGE:
        strikes = redis_client.incr(_strikes_key(phone_number))
        redis_client.expire(_strikes_key(phone_number), _STRIKE_COUNTER_TTL)
        redis_client.set(_stage_key(phone_number), 0)
        if strikes >= _BAN_STRIKE_LIMIT:
            _ban_permanently(phone_number)
            redis_client.delete(_strikes_key(phone_number))
    else:
        redis_client.set(_stage_key(phone_number), stage + 1)


def register_success(phone_number: str) -> None:
    """Call once a login fully succeeds (OTP verified correctly).
    Clears every piece of throttle state, including the ban-strike
    streak."""
    redis_client.delete(_lock_key(phone_number))
    redis_client.delete(_attempts_key(phone_number))
    redis_client.delete(_stage_key(phone_number))
    redis_client.delete(_strikes_key(phone_number))


def _ban_permanently(phone_number: str) -> None:
    User.objects.filter(phone_number=phone_number).update(is_active=False)