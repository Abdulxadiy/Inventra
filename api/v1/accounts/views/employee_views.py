"""Views for hiring and firing employees within a tenant"""

from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.models import Tenant
from apps.accounts.services.employee_service import EmployeeService, EmployeeServiceError
from api.v1.accounts.serializers import EmployeeHireSerializer, EmployeeFireSerializer, EmployeeOutputSerializer


def _resolve_tenant_or_403(request, tenant_id):
    """Fetch the tenant and confirm the requester has authority over it."""
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    if request.user.role == "platform_admin":
        return tenant, None
    if request.user.role == 'owner' and tenant.owner_id == request.user.id:
        return tenant, None
    return None, Response(
        {"detail": "You don't have authority over this tenant."},
        status=status.HTTP_403_FORBIDDEN
    )


class EmployeeHireView(APIView):
    """POST /api/v1/tenants/{tenant_id}/employees/hire/"""

    def post(self, request, tenant_id):
        tenant, error = _resolve_tenant_or_403(request, tenant_id)
        if error:
            return error

        serializer = EmployeeHireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            employee = EmployeeService.hire(
                target_user=serializer.validated_data['target_user'],
                tenant=tenant,
                hired_by=request.user,
                position=serializer.validated_data.get('position', ''),
                role="staff",
            )
        except EmployeeServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EmployeeOutputSerializer(employee).data, status=status.HTTP_201_CREATED)


class EmployeeFireView(APIView):
    """POST /api/v1/tenants/{tenant_id}/employees/fire/"""

    def post(self, request, tenant_id):
        tenant, error = _resolve_tenant_or_403(request, tenant_id)
        if error:
            return error

        serializer = EmployeeFireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            employee = EmployeeService.fire(
                target_user=serializer.validated_data["target_user"],
                fired_by=request.user
            )
        except EmployeeServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EmployeeOutputSerializer(employee).data)