"""
inventory/admin.py
==================
Django Admin configuration for Brand, Thaan, ThaanPurchase.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Brand, Thaan, ThaanPurchase


# ---------------------------------------------------------------------------
# BRAND
# ---------------------------------------------------------------------------

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display    = ("brand_id", "brand_name", "total_thaans")
    search_fields   = ("brand_name",)
    ordering        = ("brand_name",)

    def total_thaans(self, obj):
        return obj.thaans.count()
    total_thaans.short_description = "Total Thaans"


# ---------------------------------------------------------------------------
# THAAN PURCHASE (inline inside Thaan)
# ---------------------------------------------------------------------------

class ThaanPurchaseInline(admin.TabularInline):
    model       = ThaanPurchase
    extra       = 0
    fields      = ("invoice_number", "purchase_date", "price_paid", "payment_status")
    readonly_fields = ("invoice_number",)


# ---------------------------------------------------------------------------
# THAAN
# ---------------------------------------------------------------------------

@admin.register(Thaan)
class ThaanAdmin(admin.ModelAdmin):
    list_display    = (
        "thaan_no", "brand", "total_length",
        "remaining_length", "assigned_length_display",
        "status", "date_received",
    )
    list_filter     = ("status", "brand", "date_received")
    search_fields   = ("thaan_no", "brand__brand_name")
    ordering        = ("-date_received",)
    readonly_fields = ("remaining_length", "assigned_length_display")
    inlines         = [ThaanPurchaseInline]

    fieldsets = (
        ("Thaan Details", {
            "fields": ("thaan_no", "brand", "total_length", "date_received", "status")
        }),
        ("Cloth Tracking (Auto-calculated)", {
            "fields": ("remaining_length", "assigned_length_display"),
            "classes": ("collapse",),
        }),
    )

    def assigned_length_display(self, obj):
        return f"{obj.assigned_length} m"
    assigned_length_display.short_description = "Assigned Length"

    def colored_status(self, obj):
        color = "green" if obj.status == Thaan.STATUS_ACTIVE else "gray"
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_status_display()
        )
    colored_status.short_description = "Status"


# ---------------------------------------------------------------------------
# THAAN PURCHASE
# ---------------------------------------------------------------------------

@admin.register(ThaanPurchase)
class ThaanPurchaseAdmin(admin.ModelAdmin):
    list_display    = (
        "purchase_id", "thaan", "brand",
        "invoice_number", "purchase_date",
        "price_paid", "payment_status",
    )
    list_filter     = ("payment_status", "brand", "purchase_date")
    search_fields   = ("invoice_number", "thaan__thaan_no", "brand__brand_name")
    ordering        = ("-purchase_date",)
    list_editable   = ("payment_status",)