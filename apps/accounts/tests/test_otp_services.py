"""
Place at: apps/accounts/tests/test_otp_services.py

These tests hit a real Redis instance (otp_services.py builds its client
at import time from settings.REDIS_URL, so it can't be swapped for a fake
without touching that module). Point REDIS_URL at a throwaway
DB index for tests, e.g. redis://localhost:6379/15, and make sure it's
flushed between runs (the `clean_redis` fixture below does that).
"""
import time

import pytest
from django.conf import settings

from apps.accounts.services import otp_services as otp

pytestmark = pytest.mark.django_db(transaction=False)

PHONE = "+998901234567"


@pytest.fixture(autouse=True)
def clean_redis():
    otp.redis_client.flushdb()
    yield
    otp.redis_client.flushdb()


def test_generate_code_is_six_digits():
    code = otp.generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_store_then_verify_success():
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    is_valid, reason = otp.verify_code(PHONE, code)

    assert is_valid is True
    assert reason == ""


def test_verify_wrong_code_fails_but_does_not_consume_it():
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    is_valid, reason = otp.verify_code(PHONE, "000000")
    assert is_valid is False
    assert reason == "Invalid code"

    # the real code should still work on the next attempt
    is_valid, _ = otp.verify_code(PHONE, code)
    assert is_valid is True


def test_verify_code_is_single_use():
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    first = otp.verify_code(PHONE, code)
    second = otp.verify_code(PHONE, code)

    assert first[0] is True
    assert second[0] is False
    assert second[1] == "Expired"


def test_verify_without_any_stored_code_is_expired():
    is_valid, reason = otp.verify_code(PHONE, "123456")
    assert is_valid is False
    assert reason == "Expired"


def test_too_many_attempts_locks_out():
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    for _ in range(otp.MAX_ATTEMPTS):
        otp.verify_code(PHONE, "wrong")

    is_valid, reason = otp.verify_code(PHONE, code)
    assert is_valid is False
    assert reason == "Too many attempts"


def test_store_code_sets_cooldown():
    assert otp.is_in_cooldown(PHONE) is False
    otp.store_code(PHONE, otp.generate_code())
    assert otp.is_in_cooldown(PHONE) is True


def test_discard_code_clears_everything():
    code = otp.generate_code()
    otp.store_code(PHONE, code)
    otp.verify_code(PHONE, "wrong")  # bump attempts counter

    otp.discard_code(PHONE)

    assert otp.is_in_cooldown(PHONE) is False
    is_valid, reason = otp.verify_code(PHONE, code)
    assert is_valid is False
    assert reason == "Expired"


@pytest.mark.slow
def test_code_expires_after_ttl(monkeypatch):
    """Uses a monkeypatched short TTL instead of sleeping the real 300s."""
    monkeypatch.setattr(otp, "OTP_TTL_SECONDS", 1)
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    time.sleep(1.2)

    is_valid, reason = otp.verify_code(PHONE, code)
    assert is_valid is False
    assert reason == "Expired"
