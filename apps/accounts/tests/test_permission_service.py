"""
Tests for apps/accounts/services/permission_service.py -- the
Employee.permissions-backed action-permission check.
"""
import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from apps.accounts.models import Employee
from apps.accounts.services.permission_service import PermissionService
from tests.factories import PlatformAdminFactory, OwnerFactory, StaffFactory, TenantFactory, EmployeeFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def some_permission():
    """A real Permission row to grant/check against -- reuses the
    Employee model's own content type since it always exists."""
    content_type = ContentType.objects.get_for_model(Employee)
    permission, _ = Permission.objects.get_or_create(
        codename="do_the_thing",
        content_type=content_type,
        defaults={"name": "Can do the thing"},
    )
    return permission


CODENAME = "accounts.do_the_thing"


class TestPlatformAdminAndOwner:
    def test_platform_admin_always_allowed(self):
        admin = PlatformAdminFactory()
        assert PermissionService.has_permission(admin, CODENAME) is True

    def test_owner_always_allowed(self):
        owner = OwnerFactory()
        assert PermissionService.has_permission(owner, CODENAME) is True

    def test_owner_allowed_even_with_no_matching_grant_anywhere(self, some_permission):
        # Owners bypass the Employee.permissions check entirely --
        # confirms this isn't accidentally falling through to a real
        # grant lookup that happens to match.
        owner = OwnerFactory()
        assert PermissionService.has_permission(owner, "accounts.nonexistent_codename") is True


class TestStaff:
    def test_staff_with_granted_permission_allowed(self, some_permission):
        staff = StaffFactory()
        tenant = TenantFactory()
        employee = EmployeeFactory(user=staff, tenant=tenant, is_active=True)
        employee.permissions.add(some_permission)

        assert PermissionService.has_permission(staff, CODENAME) is True

    def test_staff_without_granted_permission_denied(self, some_permission):
        staff = StaffFactory()
        tenant = TenantFactory()
        EmployeeFactory(user=staff, tenant=tenant, is_active=True)
        # Permission exists but was never granted to this employee.

        assert PermissionService.has_permission(staff, CODENAME) is False

    def test_fired_staff_denied_even_though_old_grant_still_exists_on_the_row(self, some_permission):
        staff = StaffFactory()
        tenant = TenantFactory()
        employee = EmployeeFactory(user=staff, tenant=tenant, is_active=False)
        employee.permissions.add(some_permission)

        assert PermissionService.has_permission(staff, CODENAME) is False

    def test_staff_role_with_no_employee_record_at_all_denied(self):
        staff = StaffFactory()  # role="staff" but no Employee row created
        assert PermissionService.has_permission(staff, CODENAME) is False


class TestCustomerAndAnonymous:
    def test_customer_always_denied(self):
        from tests.factories import UserFactory
        customer = UserFactory()
        assert PermissionService.has_permission(customer, CODENAME) is False

    def test_none_user_denied(self):
        assert PermissionService.has_permission(None, CODENAME) is False


class TestCodenameFormat:
    def test_malformed_codename_without_app_label_raises(self):
        staff = StaffFactory()
        with pytest.raises(ValueError):
            PermissionService.has_permission(staff, "no_dot_here")