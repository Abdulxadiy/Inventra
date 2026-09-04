"""
Central action-permission check, sitting on top of Employee.permissions
(NOT user.user_permissions/Group -- see roadmap: permission checks must
read from the active Employee record so a fired/transferred employee's
old permissions never survive, which Django's built-in
user.has_perm() can't guarantee since it doesn't know about
"active employment").

Deliberately does NOT take a tenant argument -- WHICH tenant a user is
allowed to act on is a separate concern, already handled by the
existing object-level permission classes (IsTenantMember,
IsTenantOwnerOrPlatformAdmin in api/permissions.py) via
has_object_permission(). This service only answers "does this user
have this specific action-permission at all", so combine it with a
tenant-scoping permission class in any view that operates on one
tenant's data.

Role behavior:
- platform_admin: always allowed, every permission, any tenant.
- owner: always allowed, every permission -- but ONLY within their own
  tenant (Tenant.owner is a OneToOneField, so an owner structurally
  can't act on a different tenant's data once the tenant-scoping
  permission class is combined in; this service doesn't need to know
  which tenant).
- staff: allowed only if their current ACTIVE Employee record has the
  requested Permission attached.
- customer (or no active employment at all): never allowed.
"""
from apps.accounts.models import Employee


class PermissionService:
    @staticmethod
    def has_permission(user, codename: str) -> bool:
        """
        :param user: the acting User (request.user).
        :param codename: a Django-style "app_label.codename" string,
            e.g. "catalog.add_product" -- same format as the built-in
            user.has_perm().
        """
        if user is None or not getattr(user, "is_authenticated", False):
            return False

        if user.role in ("platform_admin", "owner"):
            return True

        if user.role != "staff":
            # customer, or anything else with no employment concept
            return False

        app_label, _, short_codename = codename.partition(".")
        if not short_codename:
            raise ValueError(
                f"codename must be 'app_label.codename', got: {codename!r}"
            )

        return Employee.objects.filter(
            user=user,
            is_active=True,
            permissions__content_type__app_label=app_label,
            permissions__codename=short_codename,
        ).exists()