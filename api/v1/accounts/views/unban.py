"""
View for restoring access to a permanently-banned account.

See apps/accounts/services/login_throttle.py for how a ban happens
(3 consecutive 1-day locks -> User.is_active = False). A ban has two
halves, and unban must reverse both, or the user gets a fresh
User.is_active=True but immediately re-trips a stale lock on their
very next attempt:

1. User.is_active -> True
2. All lingering throttle state (lock/attempts/stage/strikes) for
   this user, via login_throttle.register_success() -- the same
   full-reset call already used on a normal successful login.

platform_admin only (roadmap 1.1: only platform_admin acts one level
up). No self-unban: if a platform_admin's own account gets banned,
there is currently no one left to call this endpoint for them -- that
edge case is deliberately left to shell/DB access for now, same as
platform_admin creation itself (createsuperuser-only, see roadmap
"5. Ochiq dizayn" F).
"""
from requests.packages import target
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsPlatformAdmin
from apps.accounts.services import login_throttle
from api.v1.accounts.serializers import UnbanSerializer


class UnbanView(APIView):
    """POST /api/v1/auth/unban/ {target_user_id} -- platform_admin only."""

    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        serializer = UnbanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user = serializer.validated_data["target_user"]

        target_user.is_active = True
        target_user.save(update_fields=["is_active"])

        # login_throttle is keyed by username, so it only applies to
        # staff/owner/platform_admin (customers never have a username).
        # TODO: once a phone_number-keyed customer_login_throttle module
        # exists (roadmap: customer throttle, separate module), also
        # call its full-reset here using target_user.phone_number so this
        # endpoint stays the single unban entrypoint for both audiences.
        if target_user.username:
            login_throttle.register_success(target_user.username)

        return Response(
            {
                "id": target_user.id,
                "username": target_user.username,
                "is_active": target_user.is_active
             },
            status=status.HTTP_200_OK,
        )