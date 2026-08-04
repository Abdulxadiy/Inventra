from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('customer', "Xaridor"),
        ('staff', "Sotuvchi"),
        ('owner', "Do'kon egasi"),
        ('platform_admin', "Platforma administratori"),
    ]

    phone_number = models.CharField(max_length=15, unique=True)
    username = models.CharField(max_length=30, unique=True, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        null=True, blank=True, related_name='user'
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES,
        default='customer'
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.username or self.phone_number