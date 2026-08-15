from django.db import models


class TelegramContact(models.Model):
    """This model is only for save phone number and chat ID.
    Using this model helps avoid having to re-request a Telegram number or chat ID."""
    phone_number = models.CharField(max_length=20, unique=True, null=False, blank=False, db_index=True)
    chat_id = models.CharField(max_length=100, unique=True, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'telegram_contact'

    def __str__(self):
        return f"{self.phone_number} -> {self.chat_id}"
