from rest_framework.permissions import BasePermission
from django.conf import settings
import secrets


class IsInternalService(BasePermission):
    """Allow only tokens came from an internal service.
    Header: Authorization: Internal <token>"""

    def has_permission(self, request, view):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Internal '):
            return False
        token = auth_header.split('Internal ')[1].strip()
        return secrets.compare_digest(token, settings.INTERNAL_SERVICE_TOKEN)


class IsPlatformAdmin(BasePermission):
    """Allow access only authenticated platform_admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'platform_admin'
        )


class IsOwner(BasePermission):
    """Allow access only authenticated owner users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'owner'
        )


class IsOwnerOrPlatformAdmin(BasePermission):
    """Allow access to either owner or platform_admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('owner', 'platform_admin')
        )
