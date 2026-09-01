"""
Place at: apps/accounts/tests/test_otp_services.py

These tests hit a real Redis instance (otp_services.py builds its client
at import time from settings.REDIS_URL, so it can't be swapped for a fake
without touching that module). With config/settings_test.py + the
docker-compose.test.yml test infra, REDIS_URL already points at the
isolated test Redis on port 6380 — no extra config needed here.

Covers: code generation, the store/verify/discard lifecycle, the
attempt-limit lockout, and the cooldown flag — i.e. everything in
apps/accounts/services/otp_services.py.
"""
import time

import pytest
from django.conf import settings

from apps.accounts.services import otp_services as otp

# transaction=False (the pytest-django default) is fine here since none
# of these tests touch the database at all — only Redis.
pytestmark = pytest.mark.django_db(transaction=False)

PHONE = "+998901234567"


@pytest.fixture(autouse=True)
def clean_redis():
    """Runs before AND after every test in this module (autouse=True).
    otp_services.py doesn't provide any test isolation of its own —
    without this, leftover keys from one test (e.g. a cooldown flag)
    would silently break the next one.
    """
    otp.redis_client.flushdb()
    yield
    otp.redis_client.flushdb()


def test_generate_code_is_six_digits():
    # generate_code() must always return a 6-digit numeric string —
    # this is what gets sent to the user via Telegram and typed back in.
    code = otp.generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_store_then_verify_success():
    # The basic happy path: store a code, then verify with the exact
    # same code -> should succeed with no error reason.
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    is_valid, reason = otp.verify_code(PHONE, code)

    assert is_valid is True
    assert reason == ""


def test_verify_wrong_code_fails_but_does_not_consume_it():
    # A wrong guess must fail with reason='invalid_code' *without*
    # deleting the real stored code — the user should still be able to
    # enter the correct code afterwards (up to MAX_ATTEMPTS times).
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    is_valid, reason = otp.verify_code(PHONE, "000000")
    assert is_valid is False
    assert reason == "Invalid code"

    # the real code should still work on the next attempt
    is_valid, _ = otp.verify_code(PHONE, code)
    assert is_valid is True


def test_verify_code_is_single_use():
    # verify_code() deletes the stored code on success (see
    # otp_services.verify_code: "delete the code after verify because
    # one code for only one time") — a second verify with the SAME code
    # must now fail as if it never existed.
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    first = otp.verify_code(PHONE, code)
    second = otp.verify_code(PHONE, code)

    assert first[0] is True
    assert second[0] is False
    assert second[1] == "Expired"


def test_verify_without_any_stored_code_is_expired():
    # No store_code() call ever happened for this phone number -> Redis
    # has no key for it, which verify_code() reports the same way as an
    # actually-expired code ('expired').
    is_valid, reason = otp.verify_code(PHONE, "123456")
    assert is_valid is False
    assert reason == "Expired"


def test_too_many_attempts_locks_out():
    # After MAX_ATTEMPTS failed guesses, verify_code() must refuse to
    # check the code at all anymore — even a CORRECT code submitted on
    # attempt MAX_ATTEMPTS+1 must be rejected as 'too_many_attempts',
    # protecting against brute-forcing the 6-digit code.
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    for _ in range(otp.MAX_ATTEMPTS):
        otp.verify_code(PHONE, "wrong")

    is_valid, reason = otp.verify_code(PHONE, code)
    assert is_valid is False
    assert reason == "Too many attempts"


def test_store_code_sets_cooldown():
    # store_code() also sets a COOLDOWN_SECONDS flag, which is what
    # prevents a user from spamming "resend code" requests. Checked
    # separately from the code/attempts logic since it's a distinct
    # Redis key with its own TTL.
    assert otp.is_in_cooldown(PHONE) is False
    otp.store_code(PHONE, otp.generate_code())
    assert otp.is_in_cooldown(PHONE) is True


def test_discard_code_clears_everything():
    # discard_code() exists specifically for the "Telegram delivery
    # failed" case (see its docstring in otp_services.py) — it must wipe
    # ALL three keys (code, cooldown, attempts) so the user isn't stuck
    # waiting for a code that was never actually sent, and can
    # immediately request a new one without hitting the cooldown.
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
    # Patching the module-level OTP_TTL_SECONDS constant (rather than
    # sleeping for the real 5-minute TTL) keeps this test fast while
    # still exercising real Redis expiry behaviour end-to-end. Marked
    # @pytest.mark.slow purely because it's the one test in this file
    # that still needs a real (short) sleep to let Redis's own TTL timer
    # fire.
    monkeypatch.setattr(otp, "OTP_TTL_SECONDS", 1)
    code = otp.generate_code()
    otp.store_code(PHONE, code)

    time.sleep(1.2)

    is_valid, reason = otp.verify_code(PHONE, code)
    assert is_valid is False
    assert reason == "Expired"
