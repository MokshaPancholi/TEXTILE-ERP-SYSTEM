"""
production/apps.py
"""
from django.apps import AppConfig


class ProductionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "production"
    # Production signals (Thaan.remaining_length update) live in
    # sales/signals.py to keep all auto-sync signals in one place.