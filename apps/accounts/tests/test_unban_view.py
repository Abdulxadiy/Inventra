"""
Place at: apps/accounts/tests/test_unban_view.py

API-level tests for the unban endpoint (api/v1/accounts/views/unban.py):
POST /api/v1/auth/unban/ {target_user_id} -- platform_admin only.

Covers:
- Only platform_admin can call it (401/403 for everyone else)
- Reverses User.is_active=False
- Fully clears lingering login_throttle state (lock/attempts/stage/strikes)
  so the user isn't immediately re-locked on their next login attempt
- Doesn't crash for a target with no username (customers)
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.services import login_throttle
from tests.factories import PlatformAdminFactory, StaffFactory, OwnerFactory, UserFactory

pytestmark = pytest.mark.django_db

UNBAN_URL = "/api/v1/auth/unban/"


@pytest.fixture(autouse=True)
def clean_redis():
    login_throttle.redis_client.flushdb()
    yield
    login_throttle.redis_client.flushdb()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def platform_admin():
    return PlatformAdminFactory()


def _banned_staff_with_stale_throttle():
    """A staff user who was banned by login_throttle, with the throttle
    state (lock + a leftover strike count) still sitting in Redis --
    exactly the state a real 3rd-strike ban leaves behind."""
    user = StaffFactory(is_active=False)
    login_throttle.redis_client.set(login_throttle._lock_key(user.username), "1", ex=86400)
    login_throttle.redis_client.set(login_throttle._strikes_key(user.username), "3")
    return user


class TestUnbanPermissions:
    def test_anonymous_user_rejected(self, api_client):
        target = _banned_staff_with_stale_throttle()

        response = api_client.post(UNBAN_URL, {"target_user_id": target.id})

        assert response.status_code == 401

    def test_owner_cannot_unban(self, api_client):
        target = _banned_staff_with_stale_throttle()
        owner = OwnerFactory()
        api_client.force_authenticate(user=owner)

        response = api_client.post(UNBAN_URL, {"target_user_id": target.id})

        assert response.status_code == 403
        target.refresh_from_db()
        assert target.is_active is False

    def test_staff_cannot_unban(self, api_client):
        target = _banned_staff_with_stale_throttle()
        staff = StaffFactory()
        api_client.force_authenticate(user=staff)

        response = api_client.post(UNBAN_URL, {"target_user_id": target.id})

        assert response.status_code == 403


class TestUnbanBehavior:
    def test_platform_admin_restores_access_and_clears_throttle(
        self, api_client, platform_admin
    ):
        target = _banned_staff_with_stale_throttle()
        api_client.force_authenticate(user=platform_admin)

        response = api_client.post(UNBAN_URL, {"target_user_id": target.id})

        assert response.status_code == 200
        assert response.data == {
            "id": target.id,
            "username": target.username,
            "is_active": True,
        }

        target.refresh_from_db()
        assert target.is_active is True

        locked, _ = login_throttle.is_locked(target.username)
        assert locked is False
        assert login_throttle.redis_client.get(login_throttle._strikes_key(target.username)) is None

    def test_unbanning_customer_without_username_does_not_crash(
        self, api_client, platform_admin
    ):
        # Customers never have a username, so login_throttle (username
        # -keyed) simply has nothing to clear for them -- the view must
        # skip that step instead of erroring out.
        customer = UserFactory(is_active=False)
        assert customer.username is None
        api_client.force_authenticate(user=platform_admin)

        response = api_client.post(UNBAN_URL, {"target_user_id": customer.id})

        assert response.status_code == 200
        customer.refresh_from_db()
        assert customer.is_active is True

    def test_unbanning_already_active_user_is_idempotent(self, api_client, platform_admin):
        target = StaffFactory(is_active=True)
        api_client.force_authenticate(user=platform_admin)

        response = api_client.post(UNBAN_URL, {"target_user_id": target.id})

        assert response.status_code == 200
        target.refresh_from_db()
        assert target.is_active is True

    def test_nonexistent_target_user_id_returns_400(self, api_client, platform_admin):
        api_client.force_authenticate(user=platform_admin)

        response = api_client.post(UNBAN_URL, {"target_user_id": 999999})

        assert response.status_code == 400