from django.db import models
from django.utils import timezone
from datetime import timedelta
import random

class PhoneOTP(models.Model):
    phone_number = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        expiry = self.created_at + timedelta(minutes=5)
        return not self.is_used and timezone.now() < expiry

    @staticmethod
    def generate_code():
        return str(random.randint(100000, 999999))