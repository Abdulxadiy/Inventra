"""
Place at: apps/accounts/tests/test_employee_service.py

Requires converting apps/accounts/tests.py (single file) into a
apps/accounts/tests/ package first:
    - delete/empty the old apps/accounts/tests.py
    - create apps/accounts/tests/__init__.py
    - drop this file alongside it
"""
import pytest

from apps.accounts.models import Employee
from apps.accounts.services.employee_service import (
    EmployeeService,
    EmployeeServiceError,
    PermissionDeniedError,
)
from tests.factories import (
    PlatformAdminFactory,
    OwnerFactory,
    StaffFactory,
    UserFactory,
    TenantFactory,
    EmployeeFactory,
)

pytestmark = pytest.mark.django_db


class TestHirePermissions:
    def test_platform_admin_can_hire_owner(self, platform_admin, tenant):
        target = UserFactory()
        employee = EmployeeService.hire(
            target_user=target, tenant=tenant, hired_by=platform_admin,
            role="owner", position="Owner",
        )
        assert employee.is_active is True
        target.refresh_from_db()
        assert target.role == "owner"
        assert target.tenant_id == tenant.id

    def test_owner_cannot_hire_owner(self, owner, tenant):
        target = UserFactory()
        with pytest.raises(PermissionDeniedError):
            EmployeeService.hire(
                target_user=target, tenant=tenant, hired_by=owner, role="owner",
            )

    def test_owner_can_hire_staff(self, owner, tenant):
        target = UserFactory()
        employee = EmployeeService.hire(
            target_user=target, tenant=tenant, hired_by=owner, role="staff",
        )
        assert employee.tenant_id == tenant.id
        target.refresh_from_db()
        assert target.role == "staff"

    def test_staff_cannot_hire_staff(self, tenant):
        acting_staff = StaffFactory(tenant=tenant)
        target = UserFactory()
        with pytest.raises(PermissionDeniedError):
            EmployeeService.hire(
                target_user=target, tenant=tenant, hired_by=acting_staff, role="staff",
            )

    def test_customer_cannot_hire(self, customer, tenant):
        target = UserFactory()
        with pytest.raises(PermissionDeniedError):
            EmployeeService.hire(
                target_user=target, tenant=tenant, hired_by=customer, role="staff",
            )

    def test_cannot_hire_a_platform_admin(self, platform_admin, tenant):
        other_admin = PlatformAdminFactory()
        with pytest.raises(EmployeeServiceError):
            EmployeeService.hire(
                target_user=other_admin, tenant=tenant, hired_by=platform_admin,
                role="staff",
            )

    def test_hire_rejects_unknown_role(self, platform_admin, tenant):
        target = UserFactory()
        with pytest.raises(EmployeeServiceError):
            EmployeeService.hire(
                target_user=target, tenant=tenant, hired_by=platform_admin,
                role="customer",
            )


class TestHireAutoTransfer:
    """target_user already has an active Employee elsewhere -> hire() must
    auto-fire the old one before creating the new one."""

    def test_platform_admin_transfers_staff_across_tenants(self, platform_admin):
        old_tenant = TenantFactory()
        new_tenant = TenantFactory()
        target = StaffFactory(tenant=old_tenant)
        old_employment = EmployeeFactory(user=target, tenant=old_tenant, is_active=True)

        EmployeeService.hire(
            target_user=target, tenant=new_tenant, hired_by=platform_admin, role="staff",
        )

        old_employment.refresh_from_db()
        assert old_employment.is_active is False
        assert old_employment.fired_by_id == platform_admin.id

        target.refresh_from_db()
        assert target.tenant_id == new_tenant.id
        active_employments = Employee.objects.filter(user=target, is_active=True)
        assert active_employments.count() == 1
        assert active_employments.first().tenant_id == new_tenant.id

    def test_owner_cannot_poach_staff_employed_at_another_tenant(self, owner, tenant):
        """Documents current asymmetric behaviour: hire()'s internal auto-fire
        call uses `hired_by` as the firing actor. When hired_by is an owner
        (not platform_admin), _check_fire_permission requires
        employee.tenant == fired_by.tenant, which fails for a different
        tenant's employee -> the whole hire() call raises.

        If this is NOT the intended behaviour, this test should be updated
        once the design decision is made explicit (see roadmap doc)."""
        other_tenant = TenantFactory()
        target = StaffFactory(tenant=other_tenant)
        EmployeeFactory(user=target, tenant=other_tenant, is_active=True)

        with pytest.raises(PermissionDeniedError):
            EmployeeService.hire(
                target_user=target, tenant=tenant, hired_by=owner, role="staff",
            )

    def test_hire_is_atomic_on_permission_failure(self, owner, tenant):
        """If hire() raises, no Employee/User mutation should have happened."""
        other_tenant = TenantFactory()
        target = StaffFactory(tenant=other_tenant)
        EmployeeFactory(user=target, tenant=other_tenant, is_active=True)

        with pytest.raises(PermissionDeniedError):
            EmployeeService.hire(
                target_user=target, tenant=tenant, hired_by=owner, role="staff",
            )

        target.refresh_from_db()
        assert target.tenant_id == other_tenant.id
        assert target.role == "staff"
        assert Employee.objects.filter(user=target, is_active=True).count() == 1


class TestFire:
    def test_platform_admin_can_fire_anyone(self, platform_admin, tenant):
        target = StaffFactory(tenant=tenant)
        employment = EmployeeFactory(user=target, tenant=tenant, is_active=True)

        EmployeeService.fire(target_user=target, fired_by=platform_admin)

        employment.refresh_from_db()
        assert employment.is_active is False
        assert employment.fired_by_id == platform_admin.id
        assert employment.fired_at is not None

        target.refresh_from_db()
        assert target.role == "customer"
        assert target.has_usable_password() is False

    def test_owner_can_fire_own_staff(self, owner, tenant):
        target = StaffFactory(tenant=tenant)
        EmployeeFactory(user=target, tenant=tenant, is_active=True)

        EmployeeService.fire(target_user=target, fired_by=owner)

        target.refresh_from_db()
        assert target.role == "customer"

    def test_owner_cannot_fire_staff_at_another_tenant(self, owner):
        other_tenant = TenantFactory()
        target = StaffFactory(tenant=other_tenant)
        EmployeeFactory(user=target, tenant=other_tenant, is_active=True)

        with pytest.raises(PermissionDeniedError):
            EmployeeService.fire(target_user=target, fired_by=owner)

    def test_owner_cannot_fire_another_owner(self, tenant):
        acting_owner = tenant.owner
        # A second "owner"-role user incorrectly placed in the same tenant
        # (shouldn't normally happen, but the guard must hold regardless).
        other_owner = OwnerFactory(tenant=tenant)
        EmployeeFactory(user=other_owner, tenant=tenant, is_active=True, position="Owner")

        with pytest.raises(PermissionDeniedError):
            EmployeeService.fire(target_user=other_owner, fired_by=acting_owner)

    def test_staff_cannot_fire_anyone(self, tenant):
        acting_staff = StaffFactory(tenant=tenant)
        target = StaffFactory(tenant=tenant)
        EmployeeFactory(user=target, tenant=tenant, is_active=True)

        with pytest.raises(PermissionDeniedError):
            EmployeeService.fire(target_user=target, fired_by=acting_staff)

    def test_fire_without_active_employment_raises(self, platform_admin, customer):
        with pytest.raises(EmployeeServiceError):
            EmployeeService.fire(target_user=customer, fired_by=platform_admin)

    def test_fire_preserves_history_and_tenant_on_user(self, platform_admin, tenant):
        """fired user keeps tenant/username on the User row for audit purposes
        (per roadmap 1.4), only role + password are reset."""
        target = StaffFactory(tenant=tenant, username="old_staff")
        EmployeeFactory(user=target, tenant=tenant, is_active=True)

        EmployeeService.fire(target_user=target, fired_by=platform_admin)

        target.refresh_from_db()
        assert target.tenant_id == tenant.id
        assert target.username == "old_staff"
        assert target.role == "customer"
