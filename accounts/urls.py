"""
accounts/urls.py
User management, authentication, activity logs
"""
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # Authentication
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),

    # User management
    path("create/", views.create_user, name="create_user"),
    path("list/", views.list_users, name="list_users"),
    path("profile/", views.get_user_profile, name="profile"),
    path("profile/<int:user_id>/", views.get_user_profile, name="user_profile"),

    # Activity logs
    path("activity-log/", views.activity_log, name="activity_log"),
]