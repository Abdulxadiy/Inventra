from django.urls import path
from .views import RequestOTPView, VerifyOTPView


urlpatterns = [
    path('auth/otp/request', RequestOTPView.as_view(), name='otp-request'),
    path('auth/otp/verify', VerifyOTPView.as_view(), name='otp-verify'),
]