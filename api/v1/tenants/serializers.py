"""Serializers for tenant creation and management."""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant

User = get_user_model()


class TenantCreateSerializer(serializers.ModelSerializer):
    """Validate input for creating a tenant with its owner."""

    owner_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='owner', write_only=True
    )

    class Meta:
        model = Tenant
        fields = ["id", "name", "owner_id", "description", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]


class TenantAdminSerializer(serializers.ModelSerializer):
    """Full view for platform_admin. name/description editable via PATCH;
    owner and is_active are changed only through their dedicated endpoints."""

    class Meta:
        model = Tenant
        fields = ["id", "name", "owner", "description", "is_active", "created_at"]
        read_only_fields = ["id", "owner", "is_active", "created_at"]


class TenantOwnerSerializer(serializers.ModelSerializer):
    """View for the tenant's own owner. Sees everything, edits only description."""

    class Meta:
        model = Tenant
        fields = ["id", "name", "owner", "description", "is_active", "created_at"]
        read_only_fields = ["id", "name", "owner", "is_active", "created_at"]


class TenantStaffSerializer(serializers.ModelSerializer):
    """Read-only view for staff. Same as owner's view, minus created_at."""

    class Meta:
        model = Tenant
        fields = ["id", "name", "owner", "description", "is_active"]
        read_only_fields = fields


class TenantChangeOwnerSerializer(serializers.Serializer):
    """Validates input for the change-owner endpoint."""
    new_owner_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )
