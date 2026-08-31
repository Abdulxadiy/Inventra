"""
Shared factory_boy factories used across the test suite.

Place this file at: tests/factories.py (repo root, sibling to apps/, config/)
and make sure `tests/__init__.py` exists so it is importable as `tests.factories`.
"""
import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User, Employee
from apps.tenants.models import Tenant


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    phone_number = factory.Sequence(lambda n: f"+99890{n:07d}")
    username = None
    role = "customer"
    is_active = True
    is_phone_verified = True
    profile_completed = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        # Customers never get a usable password; staff/owner/platform_admin
        # tests that need one should pass password="something" explicitly.
        if extracted:
            self.set_password(extracted)
        else:
            self.set_unusable_password()
        if create:
            self.save(update_fields=["password"])


class PlatformAdminFactory(UserFactory):
    role = "platform_admin"
    username = factory.Sequence(lambda n: f"admin{n}")
    is_staff = True


class OwnerFactory(UserFactory):
    role = "owner"
    username = factory.Sequence(lambda n: f"owner{n}")


class StaffFactory(UserFactory):
    role = "staff"
    username = factory.Sequence(lambda n: f"staff{n}")


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"Tenant {n}")
    description = ""
    is_active = True
    owner = factory.SubFactory(OwnerFactory)


class EmployeeFactory(DjangoModelFactory):
    class Meta:
        model = Employee

    user = factory.SubFactory(StaffFactory)
    tenant = factory.SubFactory(TenantFactory)
    position = "Sales"
    is_active = True
    hired_by = factory.SubFactory(PlatformAdminFactory)
