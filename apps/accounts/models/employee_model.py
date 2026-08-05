from django.contrib.auth.models import Permission
from django.utils import timezone
from django.db import models


class Employee(models.Model):
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='employments'
    )
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='employees'
    )

    position = models.CharField(max_length=100, blank=True)

    hired_at = models.DateTimeField(auto_now_add=True)
    fired_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    hired_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='hired_employees'
    )
    fired_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='fired_employees'
    )


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_active=True),
                name='unique_employment_per_user',
            )
        ]

