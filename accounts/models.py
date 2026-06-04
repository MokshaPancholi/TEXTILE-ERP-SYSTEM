"""
accounts/models.py
==================
Custom user model extending Django's AbstractUser.

Why a custom user model:
    - Django best practice: always swap out User before first migration
    - Allows adding business-specific fields (role, phone) without a separate Profile model
    - Supports role-based access: Admin, Manager, Billing Staff, Viewer

IMPORTANT:
    Set in settings.py BEFORE first migrate:
        AUTH_USER_MODEL = 'accounts.User'
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


# ---------------------------------------------------------------------------
# ROLE CHOICES
# ---------------------------------------------------------------------------

class UserRole(models.TextChoices):
    ADMIN         = "admin",         "Admin"           # full access
    MANAGER       = "manager",       "Manager"         # inventory + production
    BILLING_STAFF = "billing_staff", "Billing Staff"   # sales + billing only
    VIEWER        = "viewer",        "Viewer"          # read-only


# ---------------------------------------------------------------------------
# CUSTOM USER
# ---------------------------------------------------------------------------

class User(AbstractUser):
    """
    Extended user model for Textile ERP.

    Inherits from AbstractUser so all Django auth features work out of the box:
        - username, password, email, first_name, last_name
        - is_staff, is_active, is_superuser
        - groups, user_permissions, last_login, date_joined

    Added fields:
        - role  : business role for permission scoping
        - phone : contact number
    """

    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Enter a valid phone number (9-15 digits, optional +country code)."
    )

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.VIEWER,
        help_text="Business role controlling what this user can access."
    )
    phone = models.CharField(
        max_length=16,
        blank=True,
        default="",
        validators=[phone_validator],
        help_text="Contact phone number."
    )
    email = models.EmailField(
        unique=True,
        help_text="Required. Must be unique across all users."
    )

    class Meta:
        db_table            = "auth_user_custom"
        ordering            = ["username"]
        verbose_name        = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    # ------------------------------------------------------------------
    # Role helper properties
    # Use these in views/templates for clean permission checks
    # ------------------------------------------------------------------

    @property
    def is_admin(self):
        """Full access — all modules."""
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_manager(self):
        """Access to inventory + production modules."""
        return self.role in (UserRole.ADMIN, UserRole.MANAGER)

    @property
    def is_billing_staff(self):
        """Access to sales + billing module."""
        return self.role in (UserRole.ADMIN, UserRole.MANAGER, UserRole.BILLING_STAFF)

    @property
    def is_viewer_only(self):
        """Read-only access."""
        return self.role == UserRole.VIEWER


# ---------------------------------------------------------------------------
# USER ACTIVITY LOG
# ---------------------------------------------------------------------------

class UserActivityLog(models.Model):
    """
    Lightweight audit trail for accountability in a multi-user ERP.
    Logs important user actions: logins, bill creation, stock updates, etc.
    """

    ACTION_LOGIN          = "login"
    ACTION_LOGOUT         = "logout"
    ACTION_CREATE         = "create"
    ACTION_UPDATE         = "update"
    ACTION_DELETE         = "delete"
    ACTION_BILL_GENERATED = "bill_generated"

    ACTION_CHOICES = [
        (ACTION_LOGIN,          "Login"),
        (ACTION_LOGOUT,         "Logout"),
        (ACTION_CREATE,         "Created Record"),
        (ACTION_UPDATE,         "Updated Record"),
        (ACTION_DELETE,         "Deleted Record"),
        (ACTION_BILL_GENERATED, "Bill Generated"),
    ]

    log_id     = models.AutoField(primary_key=True)
    user       = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,      # keep logs even if user account is deleted
        null=True,
        related_name="activity_logs",
        help_text="User who performed the action."
    )
    action     = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        help_text="Type of action performed."
    )
    model_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Which model was affected (e.g. Bill, Production, KurtaStock)."
    )
    object_id  = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Primary key of the affected object."
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Human-readable description of what happened."
    )
    timestamp  = models.DateTimeField(
        auto_now_add=True,
        help_text="Exact time the action occurred."
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address from which the action was performed."
    )

    class Meta:
        db_table            = "user_activity_log"
        ordering            = ["-timestamp"]
        verbose_name        = "User Activity Log"
        verbose_name_plural = "User Activity Logs"
        indexes = [
            models.Index(fields=["user"],       name="idx_log_user"),
            models.Index(fields=["action"],     name="idx_log_action"),
            models.Index(fields=["timestamp"],  name="idx_log_timestamp"),
            models.Index(fields=["model_name"], name="idx_log_model_name"),
        ]

    def __str__(self):
        return (
            f"[{self.timestamp:%Y-%m-%d %H:%M}] "
            f"{self.user} — {self.get_action_display()} "
            f"on {self.model_name} #{self.object_id}"
        )