from django.db import models


class BaseModel(models.Model):
    tenant_name = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True