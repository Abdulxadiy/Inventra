"""
Tests for api/permissions.py::HasEmployeePermission. No real endpoint
uses this yet (nothing staff-facing exists in the codebase yet -- see
roadmap 9-bosqich, catalog/inventory), so these exercise it directly
against minimal throwaway APIViews via APIRequestFactory rather than
real URL routing.
"""
import pytest
from django.core.exceptions import ImproperlyConfigured
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from api.permissions import HasEmployeePermission
from apps.accounts.models import Employee
from tests.factories import StaffFactory, TenantFactory, EmployeeFactory

pytestmark = pytest.mark.django_db

CODENAME = "accounts.do_the_thing"
factory = APIRequestFactory()


@pytest.fixture
def some_permission():
    content_type = ContentType.objects.get_for_model(Employee)
    permission, _ = Permission.objects.get_or_create(
        codename="do_the_thing",
        content_type=content_type,
        defaults={"name": "Can do the thing"},
    )
    return permission


class _SinglePermissionView(APIView):
    permission_classes = [IsAuthenticated, HasEmployeePermission]
    required_permission = CODENAME

    def get(self, request):
        return Response({"ok": True})


class _PerMethodPermissionView(APIView):
    permission_classes = [IsAuthenticated, HasEmployeePermission]
    permission_map = {"GET": "accounts.do_the_thing", "POST": "accounts.some_other_thing"}

    def get(self, request):
        return Response({"ok": True})

    def post(self, request):
        return Response({"ok": True})


class _MisconfiguredView(APIView):
    permission_classes = [IsAuthenticated, HasEmployeePermission]
    # no required_permission, no permission_map -- deliberately broken

    def get(self, request):
        return Response({"ok": True})


class TestRequiredPermissionAttribute:
    def test_staff_with_grant_allowed(self, some_permission):
        staff = StaffFactory()
        EmployeeFactory(user=staff, tenant=TenantFactory(), is_active=True).permissions.add(
            some_permission
        )
        request = factory.get("/whatever/")
        force_authenticate(request, user=staff)

        response = _SinglePermissionView.as_view()(request)

        assert response.status_code == 200

    def test_staff_without_grant_forbidden(self):
        staff = StaffFactory()
        EmployeeFactory(user=staff, tenant=TenantFactory(), is_active=True)
        request = factory.get("/whatever/")
        force_authenticate(request, user=staff)

        response = _SinglePermissionView.as_view()(request)

        assert response.status_code == 403

    def test_misconfigured_view_raises_at_permission_check_time(self):
        staff = StaffFactory()
        request = factory.get("/whatever/")
        force_authenticate(request, user=staff)

        with pytest.raises(ImproperlyConfigured):
            _MisconfiguredView.as_view()(request)


class TestPermissionMap:
    def test_different_permission_required_per_method(self, some_permission):
        staff = StaffFactory()
        EmployeeFactory(user=staff, tenant=TenantFactory(), is_active=True).permissions.add(
            some_permission
        )

        get_request = factory.get("/whatever/")
        force_authenticate(get_request, user=staff)
        get_response = _PerMethodPermissionView.as_view()(get_request)
        assert get_response.status_code == 200  # has "do_the_thing"

        post_request = factory.post("/whatever/")
        force_authenticate(post_request, user=staff)
        post_response = _PerMethodPermissionView.as_view()(post_request)
        assert post_response.status_code == 403  # doesn't have "some_other_thing"