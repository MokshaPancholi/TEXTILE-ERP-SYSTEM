"""
sales/models.py
===============
Handles finished goods stock, billing, and sales tracking.

UPDATES APPLIED:
    - UPDATE 2:  KurtaStock.SIZE_CHOICES expanded: 32, 34, 36, 38, 40, 42, 44, 46, 48
    - UPDATE 6:  KurtaStock.clean() validates sold_quantity <= produced_quantity
    - UPDATE 7:  BillItem.clean() validates quantity <= stock.stock_quantity
    - UPDATE 8:  CheckConstraints on KurtaStock and BillItem
    - UPDATE 9:  Indexes on KurtaStock.Meta and Bill.Meta
    - UPDATE 10: FK related_names reviewed and confirmed
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
    """
    Represents finished kurtas available for sale, grouped by Thaan + Size.

    stock_quantity is NOT stored — always derived:
        stock_quantity = produced_quantity - sold_quantity

    UPDATE 2: SIZE_CHOICES now includes full range: 32, 34, 36, 38, 40, 42, 44, 46, 48.
    UPDATE 6: clean() prevents sold_quantity ever exceeding produced_quantity.
    UPDATE 8: CheckConstraints on produced_quantity and sold_quantity.
    UPDATE 9: Indexes on thaan + size.
    """

    # UPDATE 2: Full confirmed size range
    SIZE_CHOICES = [
        (32, "32"),
        (34, "34"),
        (36, "36"),
        (38, "38"),
        (40, "40"),
        (42, "42"),
        (44, "44"),
        (46, "46"),
        (48, "48"),
    ]

    stock_id = models.AutoField(primary_key=True)

    # UPDATE 10: related_name="stock_entries" — Thaan → KurtaStock
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
        # One row per Thaan+Size combination — no duplicates allowed
        unique_together     = [("thaan", "size")]
        verbose_name        = "Kurta Stock"
        verbose_name_plural = "Kurta Stock"
        # UPDATE 9: Indexes
        indexes = [
            models.Index(fields=["thaan", "size"], name="idx_stock_thaan_size"),
            models.Index(fields=["thaan"],         name="idx_stock_thaan"),
        ]
        # UPDATE 8: DB-level constraints
        constraints = [
            models.CheckConstraint(
                check=models.Q(produced_quantity__gte=0),
                name="chk_stock_produced_qty_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(sold_quantity__gte=0),
                name="chk_stock_sold_qty_non_negative",
            ),
            # sold can never exceed produced at DB level
            models.CheckConstraint(
                check=models.Q(sold_quantity__lte=models.F("produced_quantity")),
                name="chk_stock_sold_lte_produced",
            ),
        ]

    def __str__(self):
        return (
            f"Thaan #{self.thaan_id} | "
            f"Size {self.size} | "
            f"Stock: {self.stock_quantity}"
        )

    # ------------------------------------------------------------------
    # UPDATE 6: Model-level validation
    # ------------------------------------------------------------------

    def clean(self):
        """
        Ensures sold_quantity never exceeds produced_quantity.
        Raised before any save — prevents invalid stock states.
        """
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

    def save(self, *args, **kwargs):
        """Run full_clean before every save to enforce clean() validation."""
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Calculated properties (never stored)
    # ------------------------------------------------------------------

    @property
    def stock_quantity(self):
        """
        Available stock = produced - sold.
        Always computed live — never persisted — to prevent stale data.
        """
        return self.produced_quantity - self.sold_quantity

    @property
    def is_out_of_stock(self):
        """True when no stock remains. Useful for UI warnings."""
        return self.stock_quantity <= 0


# ---------------------------------------------------------------------------
# BILL
# ---------------------------------------------------------------------------

class Bill(models.Model):
    """
    Represents a single sales transaction / customer invoice.
    One Bill contains many BillItems.

    total_quantity and total_price are aggregate @properties — never stored.

    UPDATE 9: Indexes on bill_date and customer_name for fast search.
    UPDATE 10: related_name="items" on BillItem → Bill confirmed.
    """

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
        # UPDATE 9: Indexes
        indexes = [
            models.Index(fields=["bill_date"],     name="idx_bill_date"),
            models.Index(fields=["customer_name"], name="idx_bill_customer_name"),
        ]

    def __str__(self):
        return (
            f"Bill #{self.bill_no} — "
            f"{self.customer_name} — "
            f"{self.bill_date}"
        )

    # ------------------------------------------------------------------
    # Aggregate properties (computed from BillItems — never stored)
    # ------------------------------------------------------------------

    @property
    def total_quantity(self):
        """Total kurtas sold across all line items in this bill."""
        from django.db.models import Sum
        result = self.items.aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @property
    def total_price(self):
        """
        Grand total = SUM(quantity × price) across all BillItems.
        Computed fresh every call; never risks stale cached value.
        """
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
    """
    One line item within a Bill.

    Size is obtained via bill_item.stock.size — NOT stored on this model.
    Selling price is entered per transaction — NOT stored on KurtaStock.

    UPDATE 7: clean() prevents selling more than available stock_quantity.
    UPDATE 8: CheckConstraints on quantity and price.
    UPDATE 10: related_name="items" on Bill FK; related_name="bill_items" on KurtaStock FK.
    """

    item_id = models.AutoField(primary_key=True)

    # UPDATE 10: Bill → BillItem via related_name="items"
    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,       # deleting a bill removes all its line items
        related_name="items",
        help_text="Parent bill this line item belongs to."
    )
    # UPDATE 10: KurtaStock → BillItem via related_name="bill_items"
    stock = models.ForeignKey(
        KurtaStock,
        on_delete=models.PROTECT,       # never allow stock deletion if it has billing history
        related_name="bill_items",
        help_text="Stock entry being sold (provides thaan + size)."
    )

    # NOTE: No 'size' field — always access via self.stock.size
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
        # UPDATE 8: DB-level constraints
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=1),
                name="chk_bill_item_quantity_positive",
            ),
            models.CheckConstraint(
                check=models.Q(price__gt=0),
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

    # ------------------------------------------------------------------
    # UPDATE 7: Validate quantity does not exceed available stock
    # ------------------------------------------------------------------

    def clean(self):
        """
        Ensures the quantity being sold does not exceed available stock.

        Business Rule:
            BillItem.quantity <= stock.stock_quantity

        On EDIT of an existing BillItem, the old quantity is added back
        to available stock before comparing — so edits are handled correctly.

        Example:
            stock_quantity = 10 (produced=15, sold=5)
            New sale of 12 → ValidationError (only 10 available)
            Edit existing item from 3 → 8 → OK (8 <= 10)
        """
        if not self.stock_id or self.quantity is None:
            return  # required field validators handle None

        stock = self.stock

        # On edit: the previously sold qty for THIS item is still counted
        # in stock.sold_quantity, so we temporarily add it back.
        previous_qty = 0
        if self.pk:
            try:
                previous_qty = BillItem.objects.get(pk=self.pk).quantity
            except BillItem.DoesNotExist:
                previous_qty = 0

        # Effective available = current stock_quantity + what this item already holds
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
        """Run full_clean before every save to enforce clean() validation."""
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Calculated properties (never stored)
    # ------------------------------------------------------------------

    @property
    def subtotal(self):
        """Line-item total = quantity × price."""
        return self.quantity * self.price

    @property
    def size(self):
        """
        Read-only proxy to stock.size.
        Always in sync — size is never duplicated on this model.
        """
        return self.stock.size