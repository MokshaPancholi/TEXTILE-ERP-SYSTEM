"""
textile_erp/urls.py (MAIN PROJECT)
===================================
Main URL routing for Textile ERP.
Include all app-level urls here.

This file should be named urls.py in your project root.
Django setting: ROOT_URLCONF = 'textile_erp.urls'
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Admin panel
    path("admin/", admin.site.urls),

    # App-level URLs
    path("api/accounts/", include("accounts.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/production/", include("production.urls")),
    path("api/sales/", include("sales.urls")),
]