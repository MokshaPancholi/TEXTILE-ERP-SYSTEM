"""
sales/admin.py
==============
Django Admin for KurtaStock, Bill, BillItem.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
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
                '<span style="color:red; font-weight:bold;">{}</span>',
                "OUT OF STOCK"
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
        "items_summary",  # Added to merge item data view
        "total_quantity_display", "total_price_display",
        "invoice_pdf_link"
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

    def items_summary(self, obj):
        """Displays a summary of all items in the list view for easy analysis."""
        if not obj or not obj.pk:
            return "—"
        items = obj.items.all().select_related('stock')
        if not items:
            return "No items"
        summary = [f"Size {item.stock.size} (x{item.quantity})" for item in items]
        return ", ".join(summary)
    items_summary.short_description = "Purchased Items"

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

    def invoice_pdf_link(self, obj):
        if not obj or not obj.pk:
            return "—"
        url = reverse('sales:generate_bill_pdf', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" target="_blank" '
            'style="background-color:#417690; color:white; padding:4px 8px; border-radius:4px;">'
            'Download Invoice</a>', url
        )
    invoice_pdf_link.short_description = "Action"


# ---------------------------------------------------------------------------
# BILL ITEM (standalone)
# ---------------------------------------------------------------------------

@admin.register(BillItem)
class BillItemAdmin(admin.ModelAdmin):
    list_display    = (
        "item_id", "bill", "stock",
        "size_display", "quantity",
        "price", "subtotal_display",
    )
    list_filter     = ("stock__size", "bill__bill_date")
    search_fields   = ("bill__customer_name", "bill__bill_no", "stock__thaan__thaan_no")
    ordering        = ("bill",)
    readonly_fields = ("size_display", "subtotal_display")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ("size_display", "subtotal_display")

    def size_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        return obj.size
    size_display.short_description = "Size"

    def subtotal_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        if obj.quantity is None or obj.price is None:
            return "—"
        return f"₹{obj.subtotal}"
    subtotal_display.short_description = "Subtotal"