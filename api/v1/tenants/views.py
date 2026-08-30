"""View for tenant creation and management."""

from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsPlatformAdmin, IsTenantMember, IsTenantOwnerOrPlatformAdmin
from apps.tenants.models import Tenant
from apps.tenants.services import TenantService, TenantServiceError
from .serializers import (
    TenantCreateSerializer,
    TenantAdminSerializer,
    TenantChangeOwnerSerializer,
    TenantOwnerSerializer,
    TenantStaffSerializer
)


class TenantCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/tenants/ -- list all tenants (platform_admin only).
    POST /api/v1/tenants/ -- create a new tenant with its owner (platform_admin only).
    """
    serializer_class = TenantCreateSerializer
    permission_classes = [IsPlatformAdmin]

    def get_serializer_class(self):
        return TenantCreateSerializer if self.request.method == 'POST' else TenantAdminSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tenant = TenantService.create_with_owner(
                name=serializer.validated_data['name'],
                owner_user=serializer.validated_data['owner'],
                created_by=request.user,
                description=serializer.validated_data.get('description', ""),
            )
        except TenantServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TenantAdminSerializer(tenant).data, status=status.HTTP_201_CREATED)


class TenantDetailView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/v1/tenants/<tenant_pk>/ -- view or edit a single tenant.
    Access and edit rights depend on the requesting user's role.
    """

    queryset = Tenant.objects.all()
    permission_classes = [IsTenantMember]

    def get_serializer_class(self):
        role = self.request.user.role
        if role == "platform_admin":
            return TenantAdminSerializer
        elif role == "owner":
            return TenantOwnerSerializer
        return TenantStaffSerializer

    def update(self, request, *args, **kwargs):
        if request.user.role == "staff":
            return Response(
                {"detail": "Staff cannot edit tenant information."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)


class TenantChangeOwnerView(APIView):
    """POST /api/v1/tenants/<tenant_pk>/change-owner/ -- platform_admin only."""

    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        serializer = TenantChangeOwnerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            TenantService.change_owner(
                tenant=tenant,
                new_owner=serializer.validated_data['new_owner_id'],
                changed_by=request.user,
            )
        except TenantServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TenantAdminSerializer(tenant).data)


class TenantDeactivateView(APIView):
    """POST /api/v1/tenants/<tenant_pk>/deactivate/ -- platform_admin (any) oe owner (own)"""

    permission_classes = [IsTenantOwnerOrPlatformAdmin]

    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        self.check_object_permissions(request, tenant)
        tenant.is_active = False
        tenant.save(update_fields=["is_active"])
        return Response({"id": tenant.id, "is_active": tenant.is_active})


class TenantActivate(APIView):
    """POST /api/v1/tenants/{id}/activate/ — platform_admin (any) or owner (own)."""

    permission_classes = [IsTenantOwnerOrPlatformAdmin]

    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        self.check_object_permissions(request, tenant)
        tenant.is_active = True
        tenant.save(update_fields=["is_active"])
        return Response({"id": tenant.id, "is_active": tenant.is_active})
