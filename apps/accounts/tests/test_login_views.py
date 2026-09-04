"""
API-level tests for the customer phone-OTP login flow
(api/v1/accounts/views/login.py), now with customer_login_throttle
wired into both steps.
"""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.services import customer_login_throttle as throttle
from apps.accounts.services import otp_services as otp
from apps.tg_bot.models import TelegramContact
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LOGIN_REQUEST_URL = "/api/v1/auth/login/request-otp/"
LOGIN_VERIFY_URL = "/api/v1/auth/login/verify-otp/"


@pytest.fixture(autouse=True)
def clean_redis():
    throttle.redis_client.flushdb()
    yield
    throttle.redis_client.flushdb()


@pytest.fixture(autouse=True)
def mock_telegram_send():
    with patch("api.v1.accounts.views.misc.send_telegram_message", return_value=True) as mock:
        yield mock


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer_with_telegram():
    user = UserFactory()
    TelegramContact.objects.create(phone_number=user.phone_number, chat_id="12345")
    return user


def _real_otp_code(phone_number):
    return otp.redis_client.get(otp._otp_key(phone_number))


class TestLoginRequestThrottle:
    def test_successful_request_registers_one_attempt(self, api_client, customer_with_telegram):
        response = api_client.post(
            LOGIN_REQUEST_URL, {"phone_number": customer_with_telegram.phone_number}
        )

        assert response.status_code == 200
        key = throttle._attempts_key(customer_with_telegram.phone_number)
        assert throttle.redis_client.get(key) == "1"

    def test_banned_customer_cannot_request_a_new_otp(self, api_client, customer_with_telegram):
        customer_with_telegram.is_active = False
        customer_with_telegram.save(update_fields=["is_active"])

        response = api_client.post(
            LOGIN_REQUEST_URL, {"phone_number": customer_with_telegram.phone_number}
        )

        assert response.status_code == 429


class TestLoginVerifyThrottle:
    def test_wrong_code_registers_an_attempt(self, api_client, customer_with_telegram):
        api_client.post(LOGIN_REQUEST_URL, {"phone_number": customer_with_telegram.phone_number})
        # The successful request above already registered 1 attempt --
        # flush it so this test isolates the verify-side behavior.
        throttle.redis_client.delete(throttle._attempts_key(customer_with_telegram.phone_number))

        response = api_client.post(
            LOGIN_VERIFY_URL,
            {"phone_number": customer_with_telegram.phone_number, "verification_code": "000000"},
        )

        assert response.status_code == 400
        key = throttle._attempts_key(customer_with_telegram.phone_number)
        assert throttle.redis_client.get(key) == "1"

    def test_correct_code_issues_tokens_and_clears_throttle(self, api_client, customer_with_telegram):
        api_client.post(LOGIN_REQUEST_URL, {"phone_number": customer_with_telegram.phone_number})
        code = _real_otp_code(customer_with_telegram.phone_number)
        assert code is not None

        response = api_client.post(
            LOGIN_VERIFY_URL,
            {"phone_number": customer_with_telegram.phone_number, "verification_code": code},
        )

        assert response.status_code == 200
        assert set(response.data.keys()) == {"access", "refresh", "needs_profile_completion"}

        locked, _ = throttle.is_locked(customer_with_telegram.phone_number)
        assert locked is False

    def test_locked_customer_rejected_before_code_is_even_checked(
        self, api_client, customer_with_telegram
    ):
        for _ in range(5):
            throttle.register_attempt(customer_with_telegram.phone_number)

        response = api_client.post(
            LOGIN_VERIFY_URL,
            {"phone_number": customer_with_telegram.phone_number, "verification_code": "000000"},
        )

        assert response.status_code == 429
        assert "retry_after_seconds" in response.data