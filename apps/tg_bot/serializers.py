from rest_framework import serializers
from models import TelegramContact


class TelegramContactSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    chat_id = serializers.CharField(max_length=100)

    def save(self, **kwargs):
        phone_number = self.validated_data['phone_number']
        chat_id = self.validated_data['chat_id']
        obj, created = TelegramContact.objects.update_or_create(
            phone_number=phone_number,
            defaults={'chat_id': chat_id},
        )
        return obj