"""
Place at: apps/accounts/tests/test_admin_login_views.py

API-level (integration) tests for the admin-panel login flow:
username+password (step 1) -> Telegram OTP (step 2) -> JWT tokens, with
progressive throttling and a permanent-ban escalation on top.

Covers:
- api/v1/accounts/views/admin_login.py  (AdminLoginView, AdminLoginVerifyOTPView)
- apps/accounts/services/login_throttle.py (the 5/3/1 -> ban state machine)

These are the first API/view-level tests in the project — everything
before this tested the service layer directly. Uses a real Redis (both
otp_services and login_throttle build their client from the same
settings.REDIS_URL) and DRF's APIClient to exercise the actual URL
routing + views, not just the underlying functions.
"""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.services import login_throttle
from apps.accounts.services import otp_services as otp
from apps.tg_bot.models import TelegramContact
from tests.factories import StaffFactory

pytestmark = pytest.mark.django_db

ADMIN_LOGIN_URL = "/api/v1/auth/admin-login/"
ADMIN_LOGIN_VERIFY_URL = "/api/v1/auth/admin-login/verify-otp/"
PASSWORD = "CorrectHorseBatteryStaple1"


@pytest.fixture(autouse=True)
def clean_redis():
    """Both otp_services and login_throttle build their Redis client from
    the same settings.REDIS_URL, so flushing via either clears state for
    both — matches the clean_redis fixture in test_otp_services.py."""
    login_throttle.redis_client.flushdb()
    yield
    login_throttle.redis_client.flushdb()


@pytest.fixture(autouse=True)
def mock_telegram_send():
    """Every test in this module gets a working (mocked) Telegram
    delivery by default, so tests don't need to touch the real bot API."""
    with patch("api.v1.accounts.views.misc.send_telegram_message", return_value=True) as mock:
        yield mock


@pytest.fixture
def api_client():
    # Named api_client (not `client`) to avoid shadowing pytest-django's
    # own `client` fixture (django.test.Client) — we specifically need
    # DRF's APIClient here.
    return APIClient()


@pytest.fixture
def staff_with_credentials(db):
    """A staff user who has already completed the admin-login credential
    setup: a real username (StaffFactory default), a known password, and
    a linked TelegramContact so OTP delivery can succeed."""
    user = StaffFactory(password=PASSWORD)
    TelegramContact.objects.create(phone_number=user.phone_number, chat_id="12345")
    return user


def _real_otp_code(phone_number):
    """Reach into otp_services' Redis key directly to read back the code
    that was actually sent — the test has no other way to 'receive' the
    Telegram message."""
    return otp.redis_client.get(otp._otp_key(phone_number))


class TestAdminLoginPasswordStep:
    """POST /auth/admin-login/ — step 1: username + password."""

    def test_wrong_password_rejected_generically(self, api_client, staff_with_credentials):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"username": staff_with_credentials.username, "password": "wrong"},
        )

        assert response.status_code == 401
        assert response.data["detail"] == "Username or password incorrect!"

    def test_nonexistent_username_rejected_identically(self, api_client, staff_with_credentials):
        # The response for a wrong password on a REAL username must be
        # identical to a username that doesn't exist at all — otherwise
        # an attacker can enumerate valid usernames by comparing errors.
        wrong_password = api_client.post(
            ADMIN_LOGIN_URL,
            {"username": staff_with_credentials.username, "password": "wrong"},
        )
        nonexistent = api_client.post(
            ADMIN_LOGIN_URL,
            {"username": "no-such-user", "password": "whatever"},
        )

        assert nonexistent.status_code == wrong_password.status_code == 401
        assert nonexistent.data == wrong_password.data

    def test_correct_password_sends_masked_otp_hint(self, api_client, staff_with_credentials):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"username": staff_with_credentials.username, "password": PASSWORD},
        )

        assert response.status_code == 200
        # StaffFactory always builds numbers as "+99890" + a 7-digit
        # sequence (see tests/factories.py), so the operator code is
        # always "90" — only the last 2 digits vary per test run.
        expected_hint = f"+998 90 *** ** {staff_with_credentials.phone_number[-2:]}"
        assert response.data["phone_hint"] == expected_hint
        # The full phone number must never appear anywhere in the response.
        assert staff_with_credentials.phone_number not in str(response.data)


class TestAdminLoginOTPStep:
    """POST /auth/admin-login/verify-otp/ — step 2: username + OTP code."""

    def test_wrong_otp_rejected_generically(self, api_client, staff_with_credentials):
        api_client.post(
            ADMIN_LOGIN_URL,
            {"username": staff_with_credentials.username, "password": PASSWORD},
        )

        response = api_client.post(
            ADMIN_LOGIN_VERIFY_URL,
            {"username": staff_with_credentials.username, "verification_code": "000000"},
        )

        assert response.status_code == 401
        assert response.data["detail"] == "Verification code incorrect!"

    def test_correct_otp_issues_tokens_and_clears_throttle(self, api_client, staff_with_credentials):
        api_client.post(
            ADMIN_LOGIN_URL,
            {"username": staff_with_credentials.username, "password": PASSWORD},
        )
        code = _real_otp_code(staff_with_credentials.phone_number)
        assert code is not None  # sanity check: step 1 actually stored a code

        response = api_client.post(
            ADMIN_LOGIN_VERIFY_URL,
            {"username": staff_with_credentials.username, "verification_code": code},
        )

        assert response.status_code == 200
        assert set(response.data.keys()) == {"access", "refresh"}

        locked, _ = login_throttle.is_locked(staff_with_credentials.username)
        assert locked is False


class TestLoginThrottleStateMachine:
    """Whitebox tests against login_throttle.py directly — same style as
    test_otp_services.py. Lock expiry is simulated by deleting the Redis
    lock key directly instead of sleeping for real (60s/1hr/1day would
    make the suite unusably slow); from register_failure()'s point of
    view, an expired key and a deleted key are indistinguishable."""

    USERNAME = "throttletarget"

    def _expire_lock(self):
        login_throttle.redis_client.delete(login_throttle._lock_key(self.USERNAME))

    def _exhaust_one_full_cycle(self):
        """5 -> 3 -> 1 failures, expiring the lock between each stage —
        one complete cycle ending in a 1-day lock (one strike)."""
        for _ in range(5):
            login_throttle.register_failure(self.USERNAME)
        self._expire_lock()
        for _ in range(3):
            login_throttle.register_failure(self.USERNAME)
        self._expire_lock()
        login_throttle.register_failure(self.USERNAME)
        self._expire_lock()

    def test_stage_one_locks_after_five_failures(self):
        for _ in range(5):
            login_throttle.register_failure(self.USERNAME)

        locked, remaining = login_throttle.is_locked(self.USERNAME)
        assert locked is True
        assert 0 < remaining <= 60

    def test_stage_two_locks_after_three_more_failures(self):
        for _ in range(5):
            login_throttle.register_failure(self.USERNAME)
        self._expire_lock()

        for _ in range(3):
            login_throttle.register_failure(self.USERNAME)

        locked, remaining = login_throttle.is_locked(self.USERNAME)
        assert locked is True
        assert 3000 < remaining <= 3600

    def test_stage_three_locks_after_one_more_failure_and_registers_a_strike(self):
        for _ in range(5):
            login_throttle.register_failure(self.USERNAME)
        self._expire_lock()
        for _ in range(3):
            login_throttle.register_failure(self.USERNAME)
        self._expire_lock()

        login_throttle.register_failure(self.USERNAME)

        locked, remaining = login_throttle.is_locked(self.USERNAME)
        assert locked is True
        assert 86000 < remaining <= 86400
        assert login_throttle.redis_client.get(login_throttle._strikes_key(self.USERNAME)) == "1"

    def test_third_consecutive_strike_bans_permanently_and_clears_the_counter(self):
        user = StaffFactory(username=self.USERNAME)

        for _ in range(3):
            self._exhaust_one_full_cycle()

        user.refresh_from_db()
        assert user.is_active is False
        assert login_throttle.redis_client.get(login_throttle._strikes_key(self.USERNAME)) is None


class TestBannedAccountLogin:
    def test_banned_user_blocked_even_with_correct_password(self, api_client, staff_with_credentials):
        staff_with_credentials.is_active = False
        staff_with_credentials.save(update_fields=["is_active"])

        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"username": staff_with_credentials.username, "password": PASSWORD},
        )

        assert response.status_code == 429
        assert "blocked" in response.data["detail"]

