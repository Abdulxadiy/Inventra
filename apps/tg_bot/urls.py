from django.urls import path
from .views import RegisterTelegramContactView

urlpatterns = [
    path('internal/telegram/register', RegisterTelegramContactView.as_view(), name='telegram-register'),
]