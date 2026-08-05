from django.contrib.auth.models import Permission
from apps.core.models import BaseModel
from django.db import models


class Employee(BaseModel):
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='employments')
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
        return f"{self.user.username} | {self.tenant.name} | {self.position} | ({'faol' if self.is_active else 'tugagan'})"

