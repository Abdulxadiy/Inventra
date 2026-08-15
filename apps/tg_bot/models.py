from django.db import models


class TelegramContact(models.Model):
    phone_number = models.CharField(max_length=20, unique=True, null=False, blank=False, db_index=True)
    chat_id = models.CharField(max_length=100, unique=True, null=False, blank=False)