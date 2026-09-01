"""
Shared factory_boy factories used across the test suite.

Place this file at: tests/factories.py (repo root, sibling to apps/, config/)
and make sure `tests/__init__.py` exists so it is importable as `tests.factories`.

Why factory_boy instead of hand-rolling User.objects.create(...) in every
test: it gives every test a unique phone_number/username for free (via
factory.Sequence), and lets tests override only the fields they actually
care about instead of repeating the full field list everywhere.
"""
import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User, Employee
from apps.tenants.models import Tenant


class UserFactory(DjangoModelFactory):
    """Base factory for a plain customer User.

    Role-specific factories below (PlatformAdminFactory, OwnerFactory,
    StaffFactory) subclass this and only override `role` + `username`,
    since `username` is null for customers (they only ever authenticate
    via phone OTP — see architecture doc) but required-ish for the
    username/password roles.
    """

    class Meta:
        model = User
        # Tell factory_boy not to call .save() a second time after the
        # post_generation `password` hook below already saved the row —
        # avoids a redundant extra UPDATE per created user.
        skip_postgeneration_save = True

    # factory.Sequence guarantees a unique phone number per generated
    # instance (n increments per call), which matters because
    # phone_number is unique=True on the model.
    phone_number = factory.Sequence(lambda n: f"+99890{n:07d}")
    username = None
    role = "customer"
    is_active = True
    is_phone_verified = True
    profile_completed = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Set a real password only when the test explicitly asks for one
        (UserFactory(password="something")); otherwise mark the account
        unusable, matching how real customers behave (they never get a
        password — see EmployeeService.fire(), which calls
        set_unusable_password() when demoting someone back to customer).
        """
        if extracted:
            self.set_password(extracted)
        else:
            self.set_unusable_password()
        if create:
            self.save(update_fields=["password"])


class PlatformAdminFactory(UserFactory):
    """platform_admin users always need a real `username` (they log in
    with username+password, never OTP), and is_staff=True mirrors how
    create_superuser() sets it in managers.py."""

    role = "platform_admin"
    username = factory.Sequence(lambda n: f"admin{n}")
    is_staff = True


class OwnerFactory(UserFactory):
    """owner-role user. Does NOT automatically get a Tenant or an active
    Employee record — see the `tenant` fixture in conftest.py for a
    fully wired-up owner+tenant+employment combo."""

    role = "owner"
    username = factory.Sequence(lambda n: f"owner{n}")


class StaffFactory(UserFactory):
    """staff-role user, same caveat as OwnerFactory: no Employee record
    is created automatically. Combine with EmployeeFactory when a test
    needs the employment relationship itself, not just the role field."""

    role = "staff"
    username = factory.Sequence(lambda n: f"staff{n}")


class TenantFactory(DjangoModelFactory):
    """A Tenant row. `owner` defaults to a fresh OwnerFactory() instance
    if not overridden, so `TenantFactory()` alone is enough to get a
    fully valid tenant+owner pair for tests that don't care about the
    owner's identity specifically."""

    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"Tenant {n}")
    description = ""
    is_active = True
    owner = factory.SubFactory(OwnerFactory)


class EmployeeFactory(DjangoModelFactory):
    """An Employee row. Defaults to a staff member freshly hired by a
    freshly-created platform_admin, at a freshly-created tenant — override
    `user`/`tenant`/`hired_by` explicitly whenever the test needs these to
    line up with other objects already in scope (which is most of the
    time; the defaults mainly exist so `EmployeeFactory()` alone doesn't
    error out when a test genuinely doesn't care about the specifics).
    """

    class Meta:
        model = Employee

    user = factory.SubFactory(StaffFactory)
    tenant = factory.SubFactory(TenantFactory)
    position = "Sales"
    is_active = True
    hired_by = factory.SubFactory(PlatformAdminFactory)
