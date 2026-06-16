"""
inventory/urls.py
Brands, Thaans, Purchase tracking, Inventory reports
"""
from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    # Brands
    path("brands/create/", views.create_brand, name="create_brand"),
    path("brands/list/", views.list_brands, name="list_brands"),

    # Thaans
    path("thaans/create/", views.create_thaan, name="create_thaan"),
    path("thaans/list/", views.list_thaans, name="list_thaans"),
    path("thaans/<int:thaan_no>/", views.thaan_detail, name="thaan_detail"),

    # Purchases
    path("purchases/create/", views.create_purchase, name="create_purchase"),
    path("purchases/<int:purchase_id>/paid/", views.mark_purchase_paid, name="mark_paid"),

    # Reports
    path("reports/inventory/", views.inventory_report, name="inventory_report"),
]