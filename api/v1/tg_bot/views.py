from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import TelegramContactSerializer
from api.permissions import IsInternalService


class RegisterTelegramContactView(APIView):
    permission_classes = [IsInternalService]

    def post(self, request):
        serializer = TelegramContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
