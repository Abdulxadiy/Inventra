from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from django.db import models

User = get_user_model()


class Employee(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employments')
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
    permissions = models.ManyToManyField(
        Permission, blank=True, related_name='employees'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_active=True),
                name='unique_employment_per_user',
            )
        ]

    def __str__(self):
        status = 'faol' if self.is_active else 'tugagan'
        tenant_name = self.tenant.name if self.tenant else "tenant yo'q"
        return f"{self.user.username or self.user.phone_number} | {tenant_name} | {self.position} | ({status})"
