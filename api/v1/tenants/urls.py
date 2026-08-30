"""URL routes for the tenants API."""

from django.urls import path
from .views import (
    TenantListCreateView,
    TenantDetailView,
    TenantChangeOwnerView,
    TenantDeactivateView,
    TenantActivateView
)


urlpatterns = [
    path("", TenantListCreateView.as_view(), name="tenant-list-create"),
    path("<int:pk>/", TenantDetailView.as_view(), name="tenant-detail"),
    path("<int:pk>/change-owner/", TenantChangeOwnerView.as_view(), name="tenant-change-owner"),
    path("<int:pk>/deactivate/", TenantDeactivateView.as_view(), name="tenant-deactivate"),
    path("<int:pk>/activate/", TenantActivateView.as_view(), name="tenant-activate"),
    path("<int:tenant_id>/employees/hire/", EmployeeHireView.as_view(), name="tenant-employee-hire"),
    path("<int:tenant_id>/employees/fire/", EmployeeFireView.as_view(), name="tenant-employee-fire"),
]