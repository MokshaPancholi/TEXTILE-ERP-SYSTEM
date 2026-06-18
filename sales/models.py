"""
sales/models.py
===============
Handles finished goods stock, billing, and sales tracking.
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from inventory.models import Thaan


# ---------------------------------------------------------------------------
# KURTA STOCK
# ---------------------------------------------------------------------------

class KurtaStock(models.Model):
    SIZE_CHOICES = [
        (32, "32"), (34, "34"), (36, "36"),
        (38, "38"), (40, "40"), (42, "42"),
        (44, "44"), (46, "46"), (48, "48"),
    ]

    stock_id = models.AutoField(primary_key=True)
    thaan = models.ForeignKey(
        Thaan,
        on_delete=models.PROTECT,
        related_name="stock_entries",
        help_text="Thaan from which these kurtas were produced."
    )
    size = models.PositiveSmallIntegerField(
        choices=SIZE_CHOICES,
        help_text="Kurta size. Valid values: 32, 34, 36, 38, 40, 42, 44, 46, 48."
    )
    produced_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Total kurtas produced for this thaan + size combination."
    )
    sold_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Total kurtas sold so far. Auto-updated by signals on billing."
    )

    class Meta:
        db_table            = "kurta_stock"
        ordering            = ["thaan", "size"]
        unique_together     = [("thaan", "size")]
        verbose_name        = "Kurta Stock"
        verbose_name_plural = "Kurta Stock"
        indexes = [
            models.Index(fields=["thaan", "size"], name="idx_stock_thaan_size"),
            models.Index(fields=["thaan"],         name="idx_stock_thaan"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(produced_quantity__gte=0),
                name="chk_stock_produced_qty_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(sold_quantity__gte=0),
                name="chk_stock_sold_qty_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(sold_quantity__lte=models.F("produced_quantity")),
                name="chk_stock_sold_lte_produced",
            ),
        ]

    def __str__(self):
        return (
            f"Thaan #{self.thaan_id} | "
            f"Size {self.size} | "
            f"Stock: {self.stock_quantity}"
        )

    def clean(self):
        """
        1. Ensures sold_quantity never exceeds produced_quantity.
        2. Ensures total stocked kurtas do not exceed actual_kurtas_made by Karigars.
        """
        # Check 1: Sold cannot exceed Produced
        if (
            self.sold_quantity is not None
            and self.produced_quantity is not None
            and self.sold_quantity > self.produced_quantity
        ):
            raise ValidationError({
                "sold_quantity": (
                    f"sold_quantity ({self.sold_quantity}) cannot exceed "
                    f"produced_quantity ({self.produced_quantity})."
                )
            })

        # Check 2: Stock cannot exceed Karigar Production
        if self.thaan_id and self.produced_quantity is not None:
            from django.db.models import Sum
            from production.models import Production

            # Sum up all kurtas actually made by all karigars for this specific thaan
            total_made_by_karigars = Production.objects.filter(thaan_id=self.thaan_id).aggregate(
                total=Sum('actual_kurtas_made')
            )['total'] or 0

            # Sum up what is ALREADY in KurtaStock for this thaan
            existing_qs = KurtaStock.objects.filter(thaan_id=self.thaan_id)
            if self.pk:
                existing_qs = existing_qs.exclude(pk=self.pk)

            already_in_stock = existing_qs.aggregate(
                total=Sum('produced_quantity')
            )['total'] or 0

            new_total = already_in_stock + self.produced_quantity

            if new_total > total_made_by_karigars:
                available_to_stock = max(0, total_made_by_karigars - already_in_stock)
                raise ValidationError({
                    "produced_quantity": (
                        f"Cannot add {self.produced_quantity} to stock. "
                        f"Karigars have only made {total_made_by_karigars} total kurtas for Thaan #{self.thaan_id}. "
                        f"({already_in_stock} are already in stock. You can only stock {available_to_stock} more.)"
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def stock_quantity(self):
        return self.produced_quantity - self.sold_quantity

    @property
    def is_out_of_stock(self):
        return self.stock_quantity <= 0


# ---------------------------------------------------------------------------
# BILL
# ---------------------------------------------------------------------------

class Bill(models.Model):
    bill_no       = models.AutoField(primary_key=True)
    customer_name = models.CharField(
        max_length=200,
        help_text="Name of the customer for this bill."
    )
    bill_date     = models.DateField(
        default=timezone.now,
        help_text="Date of the sale."
    )

    class Meta:
        db_table            = "bill"
        ordering            = ["-bill_date", "-bill_no"]
        verbose_name        = "Bill"
        verbose_name_plural = "Bills"
        indexes = [
            models.Index(fields=["bill_date"],     name="idx_bill_date"),
            models.Index(fields=["customer_name"], name="idx_bill_customer_name"),
        ]

    def __str__(self):
        return f"Bill #{self.bill_no} — {self.customer_name} — {self.bill_date}"

    @property
    def total_quantity(self):
        from django.db.models import Sum
        result = self.items.aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @property
    def total_price(self):
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        result = self.items.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("price"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        )
        return result["total"] or 0


# ---------------------------------------------------------------------------
# BILL ITEM
# ---------------------------------------------------------------------------

class BillItem(models.Model):
    item_id = models.AutoField(primary_key=True)

    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Parent bill this line item belongs to."
    )
    stock = models.ForeignKey(
        KurtaStock,
        on_delete=models.PROTECT,
        related_name="bill_items",
        help_text="Stock entry being sold (provides thaan + size)."
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of kurtas sold in this line item."
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Selling price per kurta — entered manually at billing time."
    )

    class Meta:
        db_table            = "bill_item"
        ordering            = ["bill", "item_id"]
        verbose_name        = "Bill Item"
        verbose_name_plural = "Bill Items"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="chk_bill_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="chk_bill_item_price_positive",
            ),
        ]

    def __str__(self):
        return (
            f"BillItem #{self.item_id} — "
            f"Bill #{self.bill_id} | "
            f"Thaan #{self.stock.thaan_id} / "
            f"Size {self.stock.size} × {self.quantity}"
        )

    def clean(self):
        if not self.stock_id or self.quantity is None:
            return

        stock = self.stock
        previous_qty = 0
        if self.pk:
            try:
                previous_qty = BillItem.objects.get(pk=self.pk).quantity
            except BillItem.DoesNotExist:
                previous_qty = 0

        effective_available = stock.stock_quantity + previous_qty

        if self.quantity > effective_available:
            raise ValidationError({
                "quantity": (
                    f"Cannot sell {self.quantity} unit(s). "
                    f"Only {effective_available} unit(s) available in stock "
                    f"(Thaan #{stock.thaan_id}, Size {stock.size})."
                )
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return self.quantity * self.price

    @property
    def size(self):
        return self.stock.size