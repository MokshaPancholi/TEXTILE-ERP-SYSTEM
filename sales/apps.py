"""
sales/apps.py
=============
Registers all auto-sync signals when the app is ready.

Signals wired up here:
    - BillItem  post_save/post_delete → KurtaStock.sold_quantity
    - Production post_save            → Thaan.remaining_length
"""
from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "sales"

    def ready(self):
        import sales.signals  # noqa: F401