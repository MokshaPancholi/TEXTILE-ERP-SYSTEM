"""
inventory/admin.py
==================
Django Admin configuration for Brand, Thaan, ThaanPurchase.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Brand, Thaan


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

    fieldsets = (
        ("Thaan Details", {
            "fields": ("thaan_no", "brand", "total_length", "date_received", "status")
        }),
        ("Cloth Tracking (Auto-calculated)", {
            "fields": ("remaining_length", "assigned_length_display"),
            "classes": ("collapse",),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """
        On Add form: hide remaining_length (it's auto-set).
        On Edit form: show it as readonly.
        """
        if obj is None:
            # Add form - don't show remaining_length, it's auto-set
            return (
                ("Thaan Details", {
                    "fields": ("thaan_no", "brand", "total_length", "date_received", "status")
                }),
            )
        # Edit form - show readonly fields
        return self.fieldsets

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

    def get_changeform_initial_data(self, request):
        """
        Auto-populate the next Thaan Number based on the highest existing number.
        If the last entered thaan_no was 10, this will pre-fill the box with 11.
        """
        initial = super().get_changeform_initial_data(request)
        from django.db.models import Max

        # Find the highest existing thaan_no in the database
        highest_thaan = Thaan.objects.aggregate(max_no=Max('thaan_no'))['max_no']

        if highest_thaan:
            initial['thaan_no'] = highest_thaan + 1

        return initial