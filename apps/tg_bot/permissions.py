from rest_framework.permissions import BasePermission
from django.conf import settings
import secrets


class isInternalService(BasePermission):
    """Allow only tokens came from an internal service.
    Header: Authorization: Internal <token>"""

    def has_permission(self, request, view):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Internal '):
            return False
        token = auth_header.split('Internal ')[1].strip()
        return secrets.compare_digest(token, settings.INTERNAL_SERVICE_TOKEN)
