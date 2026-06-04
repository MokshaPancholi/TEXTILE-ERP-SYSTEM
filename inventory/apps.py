"""
inventory/apps.py
"""
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "inventory"
    # No signals needed in inventory — Thaan.remaining_length
    # is updated by signals in sales/signals.py (production post_save)