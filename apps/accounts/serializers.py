from  rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class PhoneNumberSerializer(serializers.Serializer):
    """For Register and Login general serializer --> Only phone number will be asked"""
    phone_number = serializers.CharField(max_length=20)


class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    verification_code = serializers.CharField(max_length=6, min_length=6)


class CompleteProfileSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=100)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def validate_username(self, username):
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError("Bu username band.")
        return username