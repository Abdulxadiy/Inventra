"""Service layer for creating tenants together with their owner."""

from apps.accounts.services.employee_service import EmployeeService, EmployeeServiceError
from django.db import transaction
from apps.tenants.models import Tenant
from django.contrib.auth import get_user_model

User = get_user_model()


class TenantServiceError(Exception):
    """Base exception for TenantService failures."""

class TenantService:
    """Encapsulates the business rules for creating and managing tenants."""

    @staticmethod
    @transaction.atomic
    def create_with_owner(
            *,
            name: str,
            owner_user: User,
            created_by: User,
            description: str = ""
    ) -> Tenant:
        """
        Create a new Tenant with owner_user as its owner, and open the
        matching 'Owner' Employee record in one atomic operation.

        Only platform_admin may call this. Rejected upfront if owner_user
        is already an owner elsewhere or is a platform_admin themselves.
        :param name:
        :param owner_user:
        :param created_by:
        :param description:
        :return Tenant:
        """
        if created_by.role != "platform_admin":
            raise TenantServiceError("Only platform_admin may create tenants.")

        if owner_user.role == "platform_admin":
            raise TenantServiceError("A platform_admin cannot be assigned as a tenant owner.")

        if Tenant.objects.filter(owner=owner_user).exists():
            raise TenantServiceError("This user already is the owner of another tenant.")

        if Tenant.objects.filter(name=name).exists():
            raise TenantServiceError(f"A tenant named '{name}' already exists.")

        tenant = Tenant.objects.create(
            name=name,
            owner=owner_user,
            description=description,
        )

        try:
            EmployeeService.hire(
                target_user=owner_user,
                tenant=tenant,
                hired_by=created_by,
                position="owner",
                role="owner",
            )
        except EmployeeServiceError as exc:
            raise TenantServiceError(str(exc)) from exc
        return tenant
