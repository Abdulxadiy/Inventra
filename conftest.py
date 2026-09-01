"""
Root conftest.py — place at repo root, next to manage.py.

pytest auto-discovers this file (no import needed) and makes every
fixture defined here available to ALL test modules in the project,
regardless of which app they live in. That's why the shared, generic
fixtures (a platform_admin, a bare owner, a fully set-up tenant, ...)
live here instead of being duplicated in each app's tests/ package.

The `db` fixture used below is provided by pytest-django: requesting it
wraps the test in a transaction that's rolled back afterwards, so every
test starts from a clean database without you having to clean up by hand.
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
    """A bare platform_admin User, no Employee/Tenant attached.

    platform_admin accounts are never hired via EmployeeService (per the
    architecture doc — they're created through the Django shell only),
    so there's no matching Employee row to set up here; the role field
    alone is enough for permission checks.
    """
    return PlatformAdminFactory()


@pytest.fixture
def owner(db):
    """A bare owner-role User with no Tenant/Employee wired up yet.

    Deliberately minimal: some tests only care about the User row itself
    (e.g. checking that a service call is denied because of `.role`),
    and don't need a real tenant/employment relationship. Use the
    `tenant` fixture below when you need a fully consistent owner.
    """
    return OwnerFactory()


@pytest.fixture
def tenant(db, owner, platform_admin):
    """A Tenant owned by `owner`, with everything a real owner would have:
    an active Employee(position="Owner") record and owner.tenant pointing
    back at this tenant.

    This mirrors the end state of TenantService.create_with_owner(), but
    is built directly through factories (skipping the service call) so
    tests that exercise fire()/hire() logic on top of it run faster and
    don't depend on TenantService already being correct.

    Because pytest caches fixture instances per test function, any test
    that requests both `owner` and `tenant` gets the SAME owner instance
    in both — there's no risk of the tenant belonging to a different
    owner object than the one visible in the test body.
    """
    t = TenantFactory(owner=owner)
    owner.tenant = t
    owner.save(update_fields=["tenant"])
    EmployeeFactory(
        user=owner, tenant=t, is_active=True, position="Owner", hired_by=platform_admin,
    )
    return t


@pytest.fixture
def staff(db):
    """A bare staff-role User with no active Employee record.

    Note: `role="staff"` alone does NOT imply a matching Employee row
    exists — some tests need that inconsistency deliberately (e.g. to
    check that a service correctly rejects a "staff" user who has no
    active employment), others need to create the Employee explicitly
    via EmployeeFactory.
    """
    return StaffFactory()


@pytest.fixture
def customer(db):
    """A plain customer User — the default role new users get, and the
    role EmployeeService.fire() demotes people back to."""
    return UserFactory()
