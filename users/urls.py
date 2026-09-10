from django.urls import path
from .views import (
    RegisterView, LoginView, RefreshTokenView, LogoutView,
    UserProfileView, UpdateProfileView, ChangePasswordView,
    VerifyEmailView, ResendVerificationView,
    ResetPasswordRequestView, ResetPasswordVerifyView,
    AdminUsersListView,CustomerListView  # Add this import
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('profile/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path('reset-password/', ResetPasswordRequestView.as_view(), name='reset-password'),
    path('reset-password/verify/', ResetPasswordVerifyView.as_view(), name='reset-password-verify'),
    
    # Admin endpoints
    path('admin/users/', AdminUsersListView.as_view(), name='admin-users-list'),  # Add this
    path('customers/', CustomerListView.as_view(), name='customer-list'),
]