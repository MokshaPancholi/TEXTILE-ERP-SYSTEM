"""
accounts/views.py
=================
Backend views for user management, authentication, activity logging.
No frontend templates — pure backend logic.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import User, UserActivityLog


# ---------------------------------------------------------------------------
# USER AUTHENTICATION
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
def user_login(request):
    """
    Backend login endpoint.
    Expected POST: username, password
    Returns: user info + success status
    Logs: user_logged_in signal triggers activity log
    """
    try:
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({
                "status": "success",
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
            })
        return JsonResponse({"status": "error", "message": "Invalid credentials"}, status=401)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def user_logout(request):
    """Logout user. Signal logs the action."""
    logout(request)
    return JsonResponse({"status": "success", "message": "Logged out"})


# ---------------------------------------------------------------------------
# USER MANAGEMENT
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
def create_user(request):
    """
    Create a new user (admin only).
    Expected POST: username, email, password, first_name, last_name, role, phone
    """
    if not request.user.is_admin:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=request.POST.get("username"),
                email=request.POST.get("email"),
                password=request.POST.get("password"),
                first_name=request.POST.get("first_name", ""),
                last_name=request.POST.get("last_name", ""),
                role=request.POST.get("role", "viewer"),
                phone=request.POST.get("phone", ""),
                is_staff=True,
            )

            UserActivityLog.objects.create(
                user=request.user,
                action=UserActivityLog.ACTION_CREATE,
                model_name="User",
                object_id=str(user.id),
                description=f"Created user {user.username}",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

        return JsonResponse({
            "status": "success",
            "user_id": user.id,
            "username": user.username,
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def list_users(request):
    """Get all users (admin/manager only)."""
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    users = User.objects.values("id", "username", "email", "role", "is_active")
    return JsonResponse({"status": "success", "users": list(users)})


@require_http_methods(["GET"])
@login_required
def get_user_profile(request, user_id=None):
    """Get user profile. If no user_id, return current user."""
    if user_id is None:
        user_id = request.user.id

    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({
            "status": "success",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "phone": user.phone,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "date_joined": user.date_joined.isoformat(),
            }
        })
    except User.DoesNotExist:
        return JsonResponse({"status": "error", "message": "User not found"}, status=404)


@require_http_methods(["GET"])
@login_required
def activity_log(request):
    """Get activity logs for current user or all (admin only)."""
    if request.user.is_admin:
        logs = UserActivityLog.objects.select_related("user").values(
            "log_id", "user__username", "action", "model_name", "object_id",
            "timestamp", "description"
        ).order_by("-timestamp")[:100]
    else:
        logs = UserActivityLog.objects.filter(user=request.user).values(
            "log_id", "action", "model_name", "object_id", "timestamp", "description"
        ).order_by("-timestamp")[:50]

    return JsonResponse({"status": "success", "logs": list(logs)})