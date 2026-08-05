from django.contrib.auth.models import Permission
from django.utils import timezone
from django.db import models


class Employee(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='employments')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='employees')
    position = models.CharField(max_length=100, null=True)