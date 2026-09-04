from rest_framework import serializers
from apps.accounts.models.employee_model import Employee
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

User = get_user_model()


class PhoneNumberSerializer(serializers.Serializer):
    """For Register and Login general serializer --> Only phone number will be asked"""
    phone_number = serializers.CharField(max_length=20)


class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    verification_code = serializers.CharField(max_length=6, min_length=6)


class CompleteProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)


class EmployeeHireSerializer(serializers.Serializer):
    """Validates input for hiring a new staff member."""

    target_user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="target_user"
    )
    position =serializers.CharField(required=False, allow_blank=True, default="")
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True, required=False, source="permissions"
    )
    role = serializers.CharField(read_only=True, default="staff")


class EmployeeFireSerializer(serializers.Serializer):
    """Validates input for firing a staff member."""

    target_user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="target_user"
    )


class EmployeeOutputSerializer(serializers.ModelSerializer):
    """Represents an Employee record in API response."""

    class Meta:
        model = Employee
        fields = ["id", "user", "tenant", "position", "is_active", "hired_at", "fired_at"]
        read_only_fields = fields


class AdminLoginSerializer(serializers.Serializer):
    """Step 1 of admin-login: username + password."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class AdminLoginVerifyOTPSerializer(serializers.Serializer):
    """Step 2 of admin-panel login: username+ the OTP code sent by step 1."""
    username = serializers.CharField()
    verification_code = serializers.CharField(max_length=6, min_length=6)


class UnbanSerializer(serializers.Serializer):
    """Validates input for restoring a permanently-banned user's access.
        Uses target_user_id (not username) so this also works for customers,
        who never have a username -- see UnbanView."""
    target_user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="target_user"
    )