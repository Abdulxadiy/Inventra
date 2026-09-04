"""
Whitebox tests against apps/accounts/services/customer_login_throttle.py
directly -- same style as the admin-panel TestLoginThrottleStateMachine
in test_admin_login_views.py. Lock expiry is simulated by deleting the
Redis lock key directly instead of sleeping for real.
"""
import pytest

from apps.accounts.services import customer_login_throttle as throttle
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

PHONE = "+998901234567"


@pytest.fixture(autouse=True)
def clean_redis():
    throttle.redis_client.flushdb()
    yield
    throttle.redis_client.flushdb()


def _expire_lock():
    throttle.redis_client.delete(throttle._lock_key(PHONE))


def _exhaust_one_full_cycle():
    """5 -> 3 -> 1 attempts, expiring the lock between each stage --
    one complete cycle ending in a 1-day lock (one strike)."""
    for _ in range(5):
        throttle.register_attempt(PHONE)
    _expire_lock()
    for _ in range(3):
        throttle.register_attempt(PHONE)
    _expire_lock()
    throttle.register_attempt(PHONE)
    _expire_lock()


def test_stage_one_locks_after_five_attempts():
    for _ in range(5):
        throttle.register_attempt(PHONE)

    locked, remaining = throttle.is_locked(PHONE)
    assert locked is True
    assert 0 < remaining <= 60


def test_stage_two_locks_after_three_more_attempts():
    for _ in range(5):
        throttle.register_attempt(PHONE)
    _expire_lock()

    for _ in range(3):
        throttle.register_attempt(PHONE)

    locked, remaining = throttle.is_locked(PHONE)
    assert locked is True
    assert 3000 < remaining <= 3600


def test_stage_three_locks_and_registers_a_strike():
    for _ in range(5):
        throttle.register_attempt(PHONE)
    _expire_lock()
    for _ in range(3):
        throttle.register_attempt(PHONE)
    _expire_lock()

    throttle.register_attempt(PHONE)

    locked, remaining = throttle.is_locked(PHONE)
    assert locked is True
    assert 86000 < remaining <= 86400
    assert throttle.redis_client.get(throttle._strikes_key(PHONE)) == "1"


def test_third_consecutive_strike_bans_permanently_and_clears_the_counter():
    user = UserFactory(phone_number=PHONE)

    for _ in range(3):
        _exhaust_one_full_cycle()

    user.refresh_from_db()
    assert user.is_active is False
    assert throttle.redis_client.get(throttle._strikes_key(PHONE)) is None


def test_successful_login_clears_all_state_including_strikes():
    # Two full cycles = 2 strikes -- one short of the 3-strike ban.
    _exhaust_one_full_cycle()
    _exhaust_one_full_cycle()
    assert throttle.redis_client.get(throttle._strikes_key(PHONE)) == "2"

    throttle.register_success(PHONE)

    locked, _ = throttle.is_locked(PHONE)
    assert locked is False
    assert throttle.redis_client.get(throttle._strikes_key(PHONE)) is None
    assert throttle.redis_client.get(throttle._stage_key(PHONE)) is None