# users/admin_urls.py
from django.urls import path

from .admin_views import (
    AdminUserListCreateView,
    AdminUserDetailView,
    AdminUserSetPasswordView,
    AdminUserActivateView,
    AdminUserDeactivateView,
    AdminUserBanView,
    AdminUserUnbanView,
    AdminUserVerifyEmailView,
    AdminUserSetRoleView,
    AdminUserStatsView,
)

app_name = 'admin_users'

urlpatterns = [
    # List + create
    path('', AdminUserListCreateView.as_view(), name='list-create'),

    # Dashboard stats — put BEFORE <int:pk> so it isn't captured as an id
    path('stats/', AdminUserStatsView.as_view(), name='stats'),

    # Retrieve + update + delete
    path('<int:pk>/', AdminUserDetailView.as_view(), name='detail'),

    # Actions
    path('<int:pk>/set-password/', AdminUserSetPasswordView.as_view(), name='set-password'),
    path('<int:pk>/activate/',     AdminUserActivateView.as_view(),     name='activate'),
    path('<int:pk>/deactivate/',   AdminUserDeactivateView.as_view(),   name='deactivate'),
    path('<int:pk>/ban/',          AdminUserBanView.as_view(),          name='ban'),
    path('<int:pk>/unban/',        AdminUserUnbanView.as_view(),        name='unban'),
    path('<int:pk>/verify-email/', AdminUserVerifyEmailView.as_view(),  name='verify-email'),
    path('<int:pk>/set-role/',     AdminUserSetRoleView.as_view(),      name='set-role'),
]