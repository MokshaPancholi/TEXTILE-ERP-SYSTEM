fr"""
sales/admin.py
==============
Django Admin configuration for KurtaStock, Bill, BillItem.
"""

from django.contrib import admin
from django.utils.html import format_html
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

    def stock_quantity_display(self, obj):
        return obj.stock_quantity
    stock_quantity_display.short_description = "Available Stock"

    def stock_status_badge(self, obj):
        if obj.is_out_of_stock:
            return format_html(
                '<span style="color:red; font-weight:bold;">OUT OF STOCK</span>'
            )
        elif obj.stock_quantity <= 5:
            return format_html(
                '<span style="color:orange; font-weight:bold;">LOW — {}</span>',
                obj.stock_quantity
            )
        return format_html(
            '<span style="color:green;">In Stock — {}</span>',
            obj.stock_quantity
        )
    stock_status_badge.short_description = "Stock Status"


# ---------------------------------------------------------------------------
# BILL ITEM (inline inside Bill)
# ---------------------------------------------------------------------------

class BillItemInline(admin.TabularInline):
    model           = BillItem
    extra           = 1
    fields          = ("stock", "quantity", "price", "subtotal_display")
    readonly_fields = ("subtotal_display",)

    def subtotal_display(self, obj):
        if obj.pk:
            return f"₹{obj.subtotal}"
        return "—"
    subtotal_display.short_description = "Subtotal"


# ---------------------------------------------------------------------------
# BILL
# ---------------------------------------------------------------------------

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display    = (
        "bill_no", "customer_name", "bill_date",
        "total_quantity_display", "total_price_display",
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

    def total_quantity_display(self, obj):
        return obj.total_quantity
    total_quantity_display.short_description = "Total Qty"

    def total_price_display(self, obj):
        return f"₹{obj.total_price}"
    total_price_display.short_description = "Total Price"


# ---------------------------------------------------------------------------
# BILL ITEM (standalone view)
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

    def size_display(self, obj):
        return obj.size
    size_display.short_description = "Size"

    def subtotal_display(self, obj):
        return f"₹{obj.subtotal}"
    subtotal_display.short_description = "Subtotal"