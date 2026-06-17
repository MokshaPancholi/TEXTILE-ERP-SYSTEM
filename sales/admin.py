"""
sales/admin.py
==============
Django Admin for KurtaStock, Bill, BillItem.

BUG FIXES:
    - All computed readonly display methods now guard against obj=None / obj.pk=None
    - get_readonly_fields() hides computed fields on Add forms
    - BillItemInline subtotal_display safe on unsaved inline rows
    - Added invoice_pdf_link to download the PDF bill directly from the Admin panel
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse  # Added for PDF generation routing
from .models import KurtaStock, Bill, BillItem


# ---------------------------------------------------------------------------
# KURTA STOCK
# ---------------------------------------------------------------------------

@admin.register(KurtaStock)
class KurtaStockAdmin(admin.ModelAdmin):
    list_display    = (
        "stock_id", "thaan", "size",
        "produced_quantity", "sold_quantity",
        "stock_quantity_display", "stock_status_badge",
    )
    list_filter     = ("size", "thaan__brand")
    search_fields   = ("thaan__thaan_no", "thaan__brand__brand_name")
    ordering        = ("thaan", "size")
    readonly_fields = ("stock_quantity_display", "stock_status_badge")

    def get_readonly_fields(self, request, obj=None):
        """Hide computed fields on Add form — no data to compute yet."""
        if obj is None:
            return ()
        return ("stock_quantity_display", "stock_status_badge")

    def stock_quantity_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        return obj.stock_quantity
    stock_quantity_display.short_description = "Available Stock"

    def stock_status_badge(self, obj):
        if not obj or not obj.pk:
            return "—"
        if obj.is_out_of_stock:
            return format_html(
                '<span style="color:red; font-weight:bold;">OUT OF STOCK</span>'
            )
        elif obj.stock_quantity <= 5:
            return format_html(
                '<span style="color:orange; font-weight:bold;">LOW — {}</span>',
                obj.stock_quantity,
            )
        return format_html(
            '<span style="color:green;">In Stock — {}</span>',
            obj.stock_quantity,
        )
    stock_status_badge.short_description = "Stock Status"


# ---------------------------------------------------------------------------
# BILL ITEM INLINE
# ---------------------------------------------------------------------------

class BillItemInline(admin.TabularInline):
    model           = BillItem
    extra           = 1
    fields          = ("stock", "quantity", "price", "subtotal_display")
    readonly_fields = ("subtotal_display",)

    def subtotal_display(self, obj):
        # Guard: inline row not yet saved has no pk
        if not obj or not obj.pk:
            return "—"
        if obj.quantity is None or obj.price is None:
            return "—"
        return f"₹{obj.subtotal}"
    subtotal_display.short_description = "Subtotal"


# ---------------------------------------------------------------------------
# BILL
# ---------------------------------------------------------------------------
@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display    = (
        "bill_no", "customer_name", "bill_date",
        "total_quantity_display", "total_price_display",
        "invoice_pdf_link"  # <--- Reference here
    )
    list_filter     = ("bill_date",)
    search_fields   = ("customer_name", "bill_no")
    ordering        = ("-bill_date",)
    readonly_fields = ("total_quantity_display", "total_price_display")
    inlines         = [BillItemInline]

    fieldsets = (
        ("Bill Info", {
            "fields": ("customer_name", "bill_date")
        }),
        ("Totals (Auto-calculated)", {
            "fields": ("total_quantity_display", "total_price_display"),
            "classes": ("collapse",),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ("Bill Info", {
                    "fields": ("customer_name", "bill_date")
                }),
            )
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ("total_quantity_display", "total_price_display")

    def total_quantity_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        return obj.total_quantity
    total_quantity_display.short_description = "Total Qty"

    def total_price_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        return f"₹{obj.total_price}"
    total_price_display.short_description = "Total Price"

    # ▼ THIS MUST BE INDENTED INSIDE THE BillAdmin CLASS ▼
    def invoice_pdf_link(self, obj):
        """Generates a button to download the PDF invoice."""
        if not obj or not obj.pk:
            return "—"
        url = reverse('sales:generate_bill_pdf', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" target="_blank" '
            'style="background-color:#417690; color:white; padding:4px 8px; border-radius:4px;">'
            'Download Invoice</a>', url
        )
    invoice_pdf_link.short_description = "Action"
    # ▲ MUST BE INDENTED INSIDE THE CLASS ▲