"""
Progressive login-attempt throttling + permanent ban for the admin-panel
(staff/owner/platform_admin) username+password+OTP login flow.

Design:
- One shared failure counter per username covers BOTH a wrong password
  (step 1) and a wrong/expired OTP (step 2) — either counts as one
  failed login attempt.
- Attempts escalate through three stages, each stricter than the last:
    stage 0: 5 attempts -> 60 second lock
    stage 1: 3 attempts -> 1 hour lock
    stage 2: 1 attempt  -> 1 day lock, and this counts as one "strike"
             toward a permanent ban
- After a stage-2 (1 day) lock expires, the cycle restarts at stage 0.
- Any successful login clears everything, including the ban-strike count.
- 3 strikes (three 1-day locks in a row, with no successful login
  breaking the streak) -> the account is permanently banned by setting
  User.is_active = False. Only a platform_admin can lift this (via a
  separate, not-yet-built unban endpoint).
- No role is exempt from this system, including platform_admin.
- Deliberately called even for a username that doesn't exist in the DB
  (see admin_login.py), so guessing usernames behaves identically to
  guessing passwords for a real one.
"""
import redis
from django.conf import settings
from django.contrib.auth import get_user_model


User = get_user_model()

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# (max_attempts, lock_seconds) per stage, in escalation order
_STAGES = [
    (5, 60),   # stage 0: 5 attempts -> 60 second lock
    (3, 3600), # stage 1: 3 attempts -> 1 hour lock
    (1, 86400) # stage 2: 1 attempt -> 1 day lock
]
_FINAL_STAGE = len(_STAGES) - 1


# Consecutive stage-2 (1 day) locks, with no successful login in
# between, before the account is permanently banned
_BAN_STRIKE_LIMIT = 3
_STRIKE_COUNTER_TTL = 60 * 60 * 24 * 7 # 7 days: must outlive the 1-day locks. TTL = Time To Live


def _stage_key(username: str) -> str:
    return f"admin_login:stage:{username}"

def _attempts_key(username: str) -> str:
    return f"admin_login:attempts:{username}"

def _lock_key(username: str) -> str:
    return f"admin_login:locked:{username}"

def _strikes_key(username: str) -> str:
    return f"admin_login:strikes:{username}"


def is_locked(username: str) -> tuple[bool, int]:
    """
    Returns (locked, seconds_remining). Call before checking the
    password AND before checking OTP.
    :param username:
    :return tuple[bool, int]:
    """
    ttl = redis_client.ttl(_lock_key(username))
    if ttl and ttl > 0:
        return True, ttl
    return False, 0


def register_failure(username: str) -> None:
    """Call after ANY failure login attempts: wrong password at step 1, or
    wrong/expired OTP at step 2."""
    stage = int(redis_client.get(_stage_key(username)) or 0)
    stage = min(stage, _FINAL_STAGE)
    max_attempts, lock_seconds = _STAGES[stage]

    attempts = redis_client.incr(_attempts_key(username))
    if attempts == 1:
        redis_client.expire(_attempts_key(username), lock_seconds + 60)

    if attempts < max_attempts:
        return

    redis_client.set(_lock_key(username), "1", ex=lock_seconds)
    redis_client.delete(_attempts_key(username))

    if stage == _FINAL_STAGE:
        strikes = redis_client.incr(_strikes_key(username))
        redis_client.expire(_strikes_key(username), _STRIKE_COUNTER_TTL)
        redis_client.set(_stage_key(username), 0)
        if strikes >= _BAN_STRIKE_LIMIT:
            _ban_permanently(username)
            redis_client.delete(_strikes_key(username))
    else:
        redis_client.set(_stage_key(username), stage + 1)


def register_success(username: str) -> None:
    """Call once login fully succeeds (correct, password AND
    correct OTP). Clears every piece of throttle state, including
    the ban-strike already streak"""
    redis_client.delete(_lock_key(username))
    redis_client.delete(_attempts_key(username))
    redis_client.delete(_stage_key(username))
    redis_client.delete(_strikes_key(username))


def _ban_permanently(username: str) -> None:
    User.objects.filter(username=username).update(is_active=False)
