"""
accounts/admin.py
=================
Django Admin for User and UserActivityLog.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserActivityLog


# ---------------------------------------------------------------------------
# CUSTOM USER ADMIN
# ---------------------------------------------------------------------------

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Extends Django's built-in UserAdmin to expose the custom role and phone fields.
    """

    list_display  = (
        "username", "email", "first_name", "last_name",
        "role_badge", "phone", "is_active", "is_staff", "date_joined",
    )
    list_filter   = ("role", "is_active", "is_staff", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    ordering      = ("username",)

    # Add role + phone into the existing UserAdmin fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ("ERP Profile", {
            "fields": ("role", "phone"),
        }),
    )

    # Show role + phone on the add-user form too
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("ERP Profile", {
            "fields": ("email", "role", "phone"),
        }),
    )

    def role_badge(self, obj):
        colors = {
            "admin":         "red",
            "manager":       "blue",
            "billing_staff": "green",
            "viewer":        "gray",
        }
        color = colors.get(obj.role, "black")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_role_display()
        )
    role_badge.short_description = "Role"


# ---------------------------------------------------------------------------
# USER ACTIVITY LOG ADMIN
# ---------------------------------------------------------------------------

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    """
    Read-only audit log — no one should edit activity logs from admin.
    """

    list_display  = (
        "log_id", "user", "action_badge",
        "model_name", "object_id",
        "ip_address", "timestamp",
    )
    list_filter   = ("action", "model_name", "timestamp")
    search_fields = ("user__username", "model_name", "object_id", "description")
    ordering      = ("-timestamp",)
    readonly_fields = (
        "user", "action", "model_name",
        "object_id", "description",
        "timestamp", "ip_address",
    )

    # Prevent add/delete from admin — logs are created only by the system
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # only superuser can purge logs

    def action_badge(self, obj):
        colors = {
            "login":          "green",
            "logout":         "gray",
            "create":         "blue",
            "update":         "orange",
            "delete":         "red",
            "bill_generated": "purple",
        }
        color = colors.get(obj.action, "black")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = "Action"