"""
production/admin.py
===================
Django Admin for Karigar, KarigarPayment, Production.

BUG FIXES:
    - readonly computed fields (remaining_kurtas_display, labour_cost_display)
      now safely return "—" when obj has no pk (Add form scenario).
    - Computed readonly fields removed from fieldsets on Add view using
      get_readonly_fields() override.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Karigar, KarigarPayment, Production


# ---------------------------------------------------------------------------
# KARIGAR PAYMENT INLINE
# ---------------------------------------------------------------------------

class KarigarPaymentInline(admin.TabularInline):
    model           = KarigarPayment
    extra           = 0
    fields          = ("payment_date", "amount_paid", "payment_status", "remarks")


# ---------------------------------------------------------------------------
# KARIGAR
# ---------------------------------------------------------------------------

@admin.register(Karigar)
class KarigarAdmin(admin.ModelAdmin):
    list_display  = ("karigar_id", "name", "total_assignments", "total_paid_display")
    search_fields = ("name",)
    ordering      = ("name",)
    inlines       = [KarigarPaymentInline]

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
    list_display  = (
        "payment_id", "karigar", "payment_date",
        "amount_paid", "payment_status", "remarks",
    )
    list_filter   = ("payment_status", "payment_date")
    search_fields = ("karigar__name",)
    ordering      = ("-payment_date",)
    list_editable = ("payment_status",)


# ---------------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------------

@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = (
        "production_id", "thaan", "karigar",
        "length_assigned", "planned_kurtas",
        "actual_kurtas_made", "remaining_kurtas_display",
        "price_per_piece", "labour_cost_display",
        "status", "date_assigned",
    )
    list_filter   = ("status", "karigar", "date_assigned")
    search_fields = ("thaan__thaan_no", "karigar__name")
    ordering      = ("-date_assigned",)

    # Computed display methods are readonly — never editable fields
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
            "fields": ("planned_kurtas", "actual_kurtas_made", "remaining_kurtas_display")
        }),
        ("Labour Cost", {
            "fields": ("price_per_piece", "labour_cost_display")
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """
        BUG FIX: On the Add form (obj is None), exclude computed readonly
        fields because the object has no data yet and properties return None.
        Only show them on the Change (edit) form where data already exists.
        """
        if obj is None:
            # Add form — hide computed fields, nothing to compute yet
            return ()
        # Change form — show computed readonly fields normally
        return ("remaining_kurtas_display", "labour_cost_display")

    # ------------------------------------------------------------------
    # Safe display methods — always guard against None
    # ------------------------------------------------------------------

    def remaining_kurtas_display(self, obj):
        """Shows remaining kurtas. Safe on unsaved objects."""
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
        """Shows total labour cost. Safe on unsaved objects."""
        if not obj or not obj.pk:
            return "—"
        val = obj.labour_cost_total
        if val is None:
            return "—"
        return f"₹{val}"
    labour_cost_display.short_description = "Labour Cost Total"