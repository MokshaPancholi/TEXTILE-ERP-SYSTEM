"""
production/admin.py
===================
Django Admin for Karigar, KarigarPayment, Production.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Karigar, KarigarPayment, Production


class KarigarPaymentInline(admin.TabularInline):
    model = KarigarPayment
    extra = 0
    fields = ("payment_date", "amount_paid", "remarks")


@admin.register(Karigar)
class KarigarAdmin(admin.ModelAdmin):
    list_display = ("karigar_id", "name", "total_assignments", "total_paid_display")
    search_fields = ("name",)
    ordering = ("name",)
    inlines = [KarigarPaymentInline]

    def total_assignments(self, obj):
        return obj.productions.count()
    total_assignments.short_description = "Assignments"

    def total_paid_display(self, obj):
        return f"₹{obj.total_paid}"
    total_paid_display.short_description = "Total Paid"


@admin.register(KarigarPayment)
class KarigarPaymentAdmin(admin.ModelAdmin):
    # 1. Added 'total_paid_display' to list_display
    list_display = (
        "payment_id", "karigar", "payment_date",
        "amount_paid", "total_paid_display", "pending_balance_display"
    )
    list_filter = ("payment_date",)
    search_fields = ("karigar__name",)
    ordering = ("-payment_date",)

    # 2. Add this method to display the total paid
    def total_paid_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        return f"₹{obj.karigar_total_paid}"
    total_paid_display.short_description = "Total Paid"

    # ... keep your existing pending_balance_display method ...
    def pending_balance_display(self, obj):
        if not obj or not obj.pk:
            return "—"

        balance = obj.karigar_balance_due

        if balance > 0:
            return format_html(
                '<span style="color:red; font-weight:bold;">₹{} Due</span>',
                balance
            )
        elif balance < 0:
            return format_html(
                '<span style="color:blue; font-weight:bold;">₹{} Advance</span>',
                abs(balance)
            )

        return format_html(
            '<span style="color:green; font-weight:bold;">{}</span>',
            "Cleared (₹0)"
        )
    pending_balance_display.short_description = "Pending Balance"


@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = (
        "production_id", "thaan", "karigar", "length_assigned",
        "planned_kurtas", "actual_kurtas_made",
        "remaining_kurtas_display", "price_per_piece",
        "labour_cost_display", "status",
    )
    list_filter = ("status", "karigar", "date_assigned")
    search_fields = ("thaan__thaan_no", "karigar__name")
    ordering = ("-date_assigned",)
    readonly_fields = ("remaining_kurtas_display", "labour_cost_display")

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ("Assignment", {
                    "fields": ("thaan", "karigar", "date_assigned", "status")
                }),
                ("Cloth", {
                    "fields": ("length_assigned", "remaining_length_after_making")
                }),
                ("Kurta Tracking", {
                    "fields": ("planned_kurtas", "actual_kurtas_made")
                }),
                ("Labour Cost", {
                    "fields": ("price_per_piece",)
                }),
            )
        return (
            ("Assignment", {
                "fields": ("thaan", "karigar", "date_assigned", "status")
            }),
            ("Cloth", {
                "fields": ("length_assigned", "remaining_length_after_making")
            }),
            ("Kurta Tracking", {
                "fields": ("planned_kurtas", "actual_kurtas_made", "remaining_kurtas_display")
            }),
            ("Labour Cost", {
                "fields": ("price_per_piece", "labour_cost_display")
            }),
        )

    def remaining_kurtas_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        val = obj.remaining_kurtas
        if val is None:
            return "—"
        color = "red" if val > 0 else "green"
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>', color, val
        )
    remaining_kurtas_display.short_description = "Remaining Kurtas"

    def labour_cost_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        val = obj.labour_cost_total
        if val is None:
            return "—"
        return f"₹{val}"
    labour_cost_display.short_description = "Labour Cost Total"