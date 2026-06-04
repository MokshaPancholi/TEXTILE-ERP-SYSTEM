"""
production/admin.py
===================
Django Admin configuration for Karigar, KarigarPayment, Production.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Karigar, KarigarPayment, Production


# ---------------------------------------------------------------------------
# KARIGAR PAYMENT (inline inside Karigar)
# ---------------------------------------------------------------------------

class KarigarPaymentInline(admin.TabularInline):
    model           = KarigarPayment
    extra           = 0
    fields          = ("payment_date", "amount_paid", "payment_status", "remarks")
    readonly_fields = ("payment_date",)


# ---------------------------------------------------------------------------
# KARIGAR
# ---------------------------------------------------------------------------

@admin.register(Karigar)
class KarigarAdmin(admin.ModelAdmin):
    list_display    = (
        "karigar_id", "name",
        "total_assignments", "total_paid_display",
    )
    search_fields   = ("name",)
    ordering        = ("name",)
    inlines         = [KarigarPaymentInline]

    def total_assignments(self, obj):
        return obj.productions.count()
    total_assignments.short_description = "Assignments"

    def total_paid_display(self, obj):
        return f"₹{obj.total_paid}"
    total_paid_display.short_description = "Total Paid"


# ---------------------------------------------------------------------------
# KARIGAR PAYMENT
# ---------------------------------------------------------------------------

@admin.register(KarigarPayment)
class KarigarPaymentAdmin(admin.ModelAdmin):
    list_display    = (
        "payment_id", "karigar", "payment_date",
        "amount_paid", "payment_status", "remarks",
    )
    list_filter     = ("payment_status", "payment_date")
    search_fields   = ("karigar__name",)
    ordering        = ("-payment_date",)
    list_editable   = ("payment_status",)


# ---------------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------------

@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display    = (
        "production_id", "thaan", "karigar",
        "length_assigned", "planned_kurtas",
        "actual_kurtas_made", "remaining_kurtas_display",
        "price_per_piece", "labour_cost_display",
        "status", "date_assigned",
    )
    list_filter     = ("status", "karigar", "date_assigned")
    search_fields   = ("thaan__thaan_no", "karigar__name")
    ordering        = ("-date_assigned",)
    readonly_fields = (
        "remaining_kurtas_display",
        "labour_cost_display",
    )

    fieldsets = (
        ("Assignment", {
            "fields": ("thaan", "karigar", "date_assigned", "status")
        }),
        ("Cloth", {
            "fields": ("length_assigned", "remaining_length_after_making")
        }),
        ("Kurta Tracking", {
            "fields": (
                "planned_kurtas", "actual_kurtas_made",
                "remaining_kurtas_display",
            )
        }),
        ("Labour Cost", {
            "fields": ("price_per_piece", "labour_cost_display")
        }),
    )

    def remaining_kurtas_display(self, obj):
        val = obj.remaining_kurtas
        color = "red" if val > 0 else "green"
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>', color, val
        )
    remaining_kurtas_display.short_description = "Remaining Kurtas"

    def labour_cost_display(self, obj):
        return f"₹{obj.labour_cost_total}"
    labour_cost_display.short_description = "Labour Cost Total"