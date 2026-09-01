"""
Place at: apps/tenants/tests/test_tenant_service.py
(convert apps/tenants/tests.py into a tests/ package the same way as accounts)

Covers TenantService.create_with_owner() and .change_owner(), which
together are the only supported way to create a Tenant with a valid
owner, or to swap a tenant's owner. Both methods are @transaction.atomic
and both delegate the actual role assignment to EmployeeService — so
these tests focus on TenantService's OWN validation (uniqueness,
platform_admin-only access) and on the atomic rollback guarantee, not on
re-testing EmployeeService's permission logic (that's already covered in
test_employee_service.py).
"""
import pytest

from apps.tenants.models import Tenant
from apps.tenants.services import TenantService, TenantServiceError
from apps.accounts.models import Employee
from tests.factories import PlatformAdminFactory, OwnerFactory, UserFactory, TenantFactory

pytestmark = pytest.mark.django_db


class TestCreateWithOwner:
    """create_with_owner() must, in one atomic step: validate the caller
    and the target owner, create the Tenant row, and hire the owner into
    it (creating the matching Employee record)."""

    def test_platform_admin_creates_tenant_with_owner(self, platform_admin):
        # The happy path: only platform_admin can call this, and a
        # brand-new plain user becomes the tenant's owner.
        candidate = UserFactory()

        tenant = TenantService.create_with_owner(
            name="Coffee Shop", owner_user=candidate, created_by=platform_admin,
        )

        assert tenant.owner_id == candidate.id
        candidate.refresh_from_db()
        # Both sides of the relationship must be consistent: Tenant.owner
        # points at candidate, AND candidate.role/tenant got updated by
        # the internal EmployeeService.hire() call.
        assert candidate.role == "owner"
        assert candidate.tenant_id == tenant.id

        # create_with_owner() hires with position="owner" specifically —
        # this is asserting that literal value, not just "some Employee
        # row exists".
        employment = Employee.objects.get(user=candidate, is_active=True)
        assert employment.tenant_id == tenant.id
        assert employment.position == "owner"

    def test_non_platform_admin_cannot_create_tenant(self, owner):
        # Tenant creation is platform_admin-only — an existing owner has
        # no authority to spin up additional tenants for other people.
        candidate = UserFactory()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Some Shop", owner_user=candidate, created_by=owner,
            )

    def test_cannot_assign_platform_admin_as_owner(self, platform_admin):
        # platform_admin accounts stay outside the tenant system entirely
        # (see EmployeeService.hire()'s matching guard) — this checks
        # TenantService rejects it up front, before even attempting the
        # hire() call.
        other_admin = PlatformAdminFactory()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Some Shop", owner_user=other_admin, created_by=platform_admin,
            )

    def test_cannot_reuse_owner_who_already_owns_a_tenant(self, platform_admin, owner, tenant):
        # Tenant.owner is a OneToOneField — one user can own at most one
        # tenant at a time. create_with_owner() must catch this itself
        # (via `Tenant.objects.filter(owner=owner_user).exists()`) rather
        # than relying on the DB to raise an IntegrityError.
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Second Shop", owner_user=owner, created_by=platform_admin,
            )

    def test_duplicate_tenant_name_rejected(self, platform_admin, tenant):
        # Tenant.name is unique=True — same idea as above, checked
        # explicitly in the service so callers get a clean
        # TenantServiceError instead of a raw DB IntegrityError.
        candidate = UserFactory()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name=tenant.name, owner_user=candidate, created_by=platform_admin,
            )

    def test_failure_rolls_back_tenant_creation(self, platform_admin, owner, tenant):
        """owner_user is already an owner -> TenantServiceError is raised
        upfront, no Tenant row should be created for the attempted name."""
        # `tenant` fixture is only requested here to make `owner` already
        # own a tenant (see conftest.py) — this is what triggers the
        # "already an owner" validation error we're asserting against.
        before = Tenant.objects.filter(name="Rollback Shop").count()
        with pytest.raises(TenantServiceError):
            TenantService.create_with_owner(
                name="Rollback Shop", owner_user=owner, created_by=platform_admin,
            )
        # Because create_with_owner() is @transaction.atomic, the failed
        # call must leave zero trace — no half-created Tenant row.
        assert Tenant.objects.filter(name="Rollback Shop").count() == before


class TestChangeOwner:
    """change_owner() must, in one atomic step: fire the current owner
    (demoting them to customer via the normal fire() flow) and hire the
    new owner — leaving exactly one active "Owner" Employee for the
    tenant at all times."""

    def test_platform_admin_changes_owner(self, platform_admin, tenant):
        # The happy path: old owner gets demoted, new owner gets
        # promoted, Tenant.owner is repointed — all three must be true
        # simultaneously afterwards.
        old_owner = tenant.owner
        new_owner_candidate = UserFactory()

        updated = TenantService.change_owner(
            tenant=tenant, new_owner=new_owner_candidate, changed_by=platform_admin,
        )

        assert updated.owner_id == new_owner_candidate.id

        old_owner.refresh_from_db()
        # Old owner goes through the exact same fire() side effects as
        # any other fired employee: demoted to customer, no active
        # Employee record left behind.
        assert old_owner.role == "customer"
        assert Employee.objects.filter(user=old_owner, is_active=True).count() == 0

        new_owner_candidate.refresh_from_db()
        assert new_owner_candidate.role == "owner"
        assert new_owner_candidate.tenant_id == tenant.id
        assert Employee.objects.filter(
            user=new_owner_candidate, tenant=tenant, is_active=True
        ).exists()

    def test_non_platform_admin_cannot_change_owner(self, owner, tenant):
        # Same restriction as create_with_owner(): only platform_admin
        # may reassign ownership, not even the tenant's own current owner.
        new_owner_candidate = UserFactory()
        with pytest.raises(TenantServiceError):
            TenantService.change_owner(
                tenant=tenant, new_owner=new_owner_candidate, changed_by=owner,
            )

    def test_cannot_set_platform_admin_as_new_owner(self, platform_admin, tenant):
        # Same guard as create_with_owner(): platform_admin accounts can
        # never become a tenant's owner.
        other_admin = PlatformAdminFactory()
        with pytest.raises(TenantServiceError):
            TenantService.change_owner(
                tenant=tenant, new_owner=other_admin, changed_by=platform_admin,
            )

    def test_cannot_reuse_owner_of_another_tenant(self, platform_admin, tenant):
        # change_owner() checks
        # `Tenant.objects.filter(owner=new_owner).exclude(pk=tenant.pk)`
        # — i.e. the new owner must not already own a DIFFERENT tenant.
        # (Note: unlike create_with_owner(), this correctly excludes the
        # current tenant itself, so "re-assigning the same owner" isn't
        # accidentally blocked — this test only covers the cross-tenant
        # conflict case.)
        other_tenant = TenantFactory()
        with pytest.raises(TenantServiceError):
            TenantService.change_owner(
                tenant=tenant, new_owner=other_tenant.owner, changed_by=platform_admin,
            )
