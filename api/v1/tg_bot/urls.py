from django.urls import path
from api.v1.tg_bot.views import RegisterTelegramContactView

urlpatterns = [
    path('internal/telegram/register/', RegisterTelegramContactView.as_view(), name='telegram-register'),
]