"""
Root conftest.py — place at repo root, next to manage.py.
Provides fixtures shared by every app's test suite.
"""
import pytest

from tests.factories import (
    PlatformAdminFactory,
    OwnerFactory,
    StaffFactory,
    UserFactory,
    TenantFactory,
    EmployeeFactory,
)


@pytest.fixture
def platform_admin(db):
    return PlatformAdminFactory()


@pytest.fixture
def owner(db):
    return OwnerFactory()


@pytest.fixture
def tenant(db, owner, platform_admin):
    """A tenant already owned by `owner`, with a matching active Employee
    record and owner.tenant set — i.e. the state you'd get after going
    through TenantService.create_with_owner(), but built directly via
    factories for speed. Use this whenever a test needs fire()/hire() to
    see a consistent, pre-existing owner employment."""
    t = TenantFactory(owner=owner)
    owner.tenant = t
    owner.save(update_fields=["tenant"])
    EmployeeFactory(
        user=owner, tenant=t, is_active=True, position="Owner", hired_by=platform_admin,
    )
    return t


@pytest.fixture
def staff(db):
    return StaffFactory()


@pytest.fixture
def customer(db):
    return UserFactory()
