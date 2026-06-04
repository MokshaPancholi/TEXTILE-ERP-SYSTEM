"""
accounts/signals.py
===================
Signals for the accounts app.

Handles:
    1. user_logged_in  → create UserActivityLog entry
    2. user_logged_out → create UserActivityLog entry
    3. user_login_failed → create UserActivityLog entry (security audit)
"""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver
from .models import UserActivityLog


def _get_ip(request):
    """Extract real IP address from request, handling proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log every successful login with IP address."""
    UserActivityLog.objects.create(
        user=user,
        action=UserActivityLog.ACTION_LOGIN,
        model_name="User",
        object_id=str(user.pk),
        description=f"{user.username} logged in successfully.",
        ip_address=_get_ip(request),
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log every logout."""
    if user:
        UserActivityLog.objects.create(
            user=user,
            action=UserActivityLog.ACTION_LOGOUT,
            model_name="User",
            object_id=str(user.pk),
            description=f"{user.username} logged out.",
            ip_address=_get_ip(request),
        )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """
    Log failed login attempts.
    Useful for detecting brute-force attempts in production.
    Does NOT store the attempted password — only the username.
    """
    attempted_username = credentials.get("username", "unknown")
    UserActivityLog.objects.create(
        user=None,                      # no user object — login failed
        action=UserActivityLog.ACTION_LOGIN,
        model_name="User",
        object_id="",
        description=f"Failed login attempt for username: '{attempted_username}'.",
        ip_address=_get_ip(request),
    )