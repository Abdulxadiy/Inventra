from django.urls import path
from api.v1.accounts.views import (
    RegisterRequestOTPView,
    RegisterVerifyOTPView,
    LoginRequestOTPView,
    LoginVerifyOTPView,
    CompleteProfileView,
    AdminLoginView,
    AdminLoginVerifyOTPView
)


urlpatterns = [
    path('auth/register/request-otp/', RegisterRequestOTPView.as_view(), name='register-request-otp'),
    path('auth/register/verify-otp/', RegisterVerifyOTPView.as_view(), name='register-verify-otp'),
    path('auth/login/request-otp/', LoginRequestOTPView.as_view(), name='login-request-otp'),
    path('auth/login/verify-otp/', LoginVerifyOTPView.as_view(), name='login-verify-otp'),
    path('auth/complete-profile/', CompleteProfileView.as_view(), name='complete-profile'),
    path('auth/admin-login/', AdminLoginView.as_view(), name='admin-login'),
    path('auth/admin-login/verify-otp/', AdminLoginVerifyOTPView.as_view(), name='admin-login-verify-otp')

]