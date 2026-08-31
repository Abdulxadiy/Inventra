"""
Place at: apps/tenants/tests/test_tenant_service.py
(convert apps/tenants/tests.py into a tests/ package the same way as accounts)
"""
import pytest

from apps.tenants.models import Tenant
from apps.tenants.services import TenantService, TenantServiceError
from apps.accounts.models import Employee
from tests.factories import PlatformAdminFactory, OwnerFactory, UserFactory, TenantFactory

pytestmark = pytest.mark.django_db


class TestCreateWithOwner:
    def test_platform_admin_creates_tenant_with_owner(self, platform_admin):
        candidate = UserFactory()

        tenant = TenantService.create_with_owner(
            name="Coffee Shop", owner_user=candidate, created_by=platform_admin,
        )

        assert tenant.owner_id == candidate.id
        candidate.refresh_from_db()
        assert candidate.role == "owner"
        assert candidate.tenant_id == tenant.id

        employment = Employee.objects.get(user=candidate, is_active=True)
        assert employment.tenant_id == tenant.id
        assert employment.position == "owner"

    def test_non_platform_admin_cannot_create_tenant(self, owner):
        candidate = UserFactory()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Some Shop", owner_user=candidate, created_by=owner,
            )

    def test_cannot_assign_platform_admin_as_owner(self, platform_admin):
        other_admin = PlatformAdminFactory()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Some Shop", owner_user=other_admin, created_by=platform_admin,
            )

    def test_cannot_reuse_owner_who_already_owns_a_tenant(self, platform_admin, owner, tenant):
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Second Shop", owner_user=owner, created_by=platform_admin,
            )

    def test_duplicate_tenant_name_rejected(self, platform_admin, tenant):
        candidate = UserFactory()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name=tenant.name, owner_user=candidate, created_by=platform_admin,
            )

    def test_failure_rolls_back_tenant_creation(self, platform_admin, owner, tenant):
        """owner_user is already an owner -> TenantServiceError is raised
        upfront, no Tenant row should be created for the attempted name."""
        before = Tenant.objects.filter(name="Rollback Shop").count()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Rollback Shop", owner_user=owner, created_by=platform_admin,
            )
        assert Tenant.objects.filter(name="Rollback Shop").count() == before


class TestChangeOwner:
    def test_platform_admin_changes_owner(self, platform_admin, tenant):
        old_owner = tenant.owner
        new_owner_candidate = UserFactory()

        updated = TenantService.change_owner(
            tenant=tenant, new_owner=new_owner_candidate, changed_by=platform_admin,
        )

        assert updated.owner_id == new_owner_candidate.id

        old_owner.refresh_from_db()
        assert old_owner.role == "customer"
        assert Employee.objects.filter(user=old_owner, is_active=True).count() == 0

        new_owner_candidate.refresh_from_db()
        assert new_owner_candidate.role == "owner"
        assert new_owner_candidate.tenant_id == tenant.id
        assert Employee.objects.filter(
            user=new_owner_candidate, tenant=tenant, is_active=True
        ).exists()

    def test_non_platform_admin_cannot_change_owner(self, owner, tenant):
        new_owner_candidate = UserFactory()
        with pytest.raises(TenantServiceError):
            TenantService.change_owner(
                tenant=tenant, new_owner=new_owner_candidate, changed_by=owner,
            )

    def test_cannot_set_platform_admin_as_new_owner(self, platform_admin, tenant):
        other_admin = PlatformAdminFactory()
        with pytest.raises(TenantServiceError):
            TenantService.change_owner(
                tenant=tenant, new_owner=other_admin, changed_by=platform_admin,
            )

    def test_cannot_reuse_owner_of_another_tenant(self, platform_admin, tenant):
        other_tenant = TenantFactory()
        with pytest.raises(TenantServiceError):
            TenantService.change_owner(
                tenant=tenant, new_owner=other_tenant.owner, changed_by=platform_admin,
            )
