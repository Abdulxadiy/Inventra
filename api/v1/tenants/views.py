"""View for tenant creation and management."""

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from api.permissions import IsPlatformAdmin
from apps.tenants.services import TenantService, TenantServiceError
from .serializers import TenantCreateSerializer


class TenantCreateView(CreateAPIView):
    serializer_class = TenantCreateSerializer
    permission_classes = [IsPlatformAdmin]

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

        output = TenantCreateSerializer(tenant)
        return Response(output.data, status=status.HTTP_201_CREATED)
