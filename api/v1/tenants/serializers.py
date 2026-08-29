"""Serializers for tenant creation and management."""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant

User = get_user_model()


class TenantCreateSerializer(serializers.ModelSerializer):
    """Validate input for creating a tenant with its owner."""

    owner_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='owner',
        write_only=True
    )

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "owner_id",
            "description",
            "is_active",
            "created_at"
        ]
        read_only_fields = [
            "id",
            "is_active",
            "created_at"
        ]
