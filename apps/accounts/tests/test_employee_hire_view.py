"""
Regression test for the hire-endpoint gap (EmployeeHireSerializer
accepted permission_ids, but the view never passed them through to
EmployeeService.hire()) -- api/v1/accounts/views/employee_views.py.
"""
import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.accounts.models import Employee
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HIRE_URL = "/api/v1/tenants/{tenant_id}/employees/hire/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def some_permission():
    content_type = ContentType.objects.get_for_model(Employee)
    permission, _ = Permission.objects.get_or_create(
        codename="do_the_thing",
        content_type=content_type,
        defaults={"name": "Can do the thing"},
    )
    return permission


def test_hire_actually_grants_the_requested_permissions(
    api_client, tenant, owner, some_permission
):
    target = UserFactory()  # a plain customer, about to be hired as staff
    api_client.force_authenticate(user=owner)

    response = api_client.post(
        HIRE_URL.format(tenant_id=tenant.id),
        {
            "target_user_id": target.id,
            "position": "Cashier",
            "permission_ids": [some_permission.id],
        },
    )

    assert response.status_code == 201
    employee = Employee.objects.get(user=target, is_active=True)
    assert list(employee.permissions.all()) == [some_permission]