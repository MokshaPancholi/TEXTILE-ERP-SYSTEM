"""
inventory/models.py
===================
Handles raw material tracking: Brands, Thaans, and Purchase records.

UPDATES APPLIED:
    - UPDATE 9: Indexes added to Thaan.Meta
    - UPDATE 8: CheckConstraints added to Thaan and ThaanPurchase
    - UPDATE 10: FK related_names reviewed and confirmed
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


# ---------------------------------------------------------------------------
# BRAND
# ---------------------------------------------------------------------------

class Brand(models.Model):
    """
    Represents a cloth supplier / brand.
    One Brand can supply many Thaans.
    """

    brand_id   = models.AutoField(primary_key=True)
    brand_name = models.CharField(
        max_length=150,
        unique=True,
        help_text="Unique brand / supplier name."
    )

    class Meta:
        db_table            = "brand"
        ordering            = ["brand_name"]
        verbose_name        = "Brand"
        verbose_name_plural = "Brands"

    def __str__(self):
        return self.brand_name


# ---------------------------------------------------------------------------
# THAAN
# ---------------------------------------------------------------------------

class Thaan(models.Model):
    """
    Represents a single roll / piece of cloth received from a brand.

    thaan_no        – manually assigned unique business identifier (e.g. 12201).
    Design Number IS the Thaan Number; no separate Design model is needed.

    remaining_length is auto-updated by signals in sales/signals.py whenever
    a Production assignment is saved.
    """

    STATUS_ACTIVE    = "active"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_ACTIVE,    "Active"),
        (STATUS_COMPLETED, "Completed"),
    ]

    # Manually assigned unique business number — NOT AutoField
    thaan_no = models.PositiveIntegerField(
        primary_key=True,
        help_text="Unique manually-assigned Thaan number (e.g. 12201)."
    )
    brand = models.ForeignKey(
        "Brand",
        on_delete=models.PROTECT,       # block deletion if thaans exist under brand
        related_name="thaans",
        help_text="Brand that supplied this thaan."
    )
    total_length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Total cloth length in metres as received."
    )
    remaining_length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Cloth still available for assignment. Auto-updated via signals."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        help_text="Active = cloth still available; Completed = fully assigned."
    )
    date_received = models.DateField(
        default=timezone.now,
        help_text="Date this thaan was received in the warehouse."
    )

    class Meta:
        db_table            = "thaan"
        ordering            = ["-date_received", "thaan_no"]
        verbose_name        = "Thaan"
        verbose_name_plural = "Thaans"
        # UPDATE 9: Indexes for common search/filter queries
        indexes = [
            models.Index(fields=["brand"],         name="idx_thaan_brand"),
            models.Index(fields=["status"],        name="idx_thaan_status"),
            models.Index(fields=["date_received"], name="idx_thaan_date_received"),
        ]
        # UPDATE 8: DB-level constraints
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_length__gt=0),
                name="chk_thaan_total_length_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(remaining_length__gte=0),
                name="chk_thaan_remaining_length_non_negative",
            ),
            # remaining_length can never exceed what was originally received
            models.CheckConstraint(
                condition=models.Q(remaining_length__lte=models.F("total_length")),
                name="chk_thaan_remaining_lte_total",
            ),
        ]

    def __str__(self):
        return f"Thaan #{self.thaan_no} — {self.brand.brand_name}"

    def save(self, *args, **kwargs):
        """
        On first creation, auto-populate remaining_length = total_length
        if the caller has not set it explicitly.
        """
        if not self.pk and self.remaining_length is None:
            self.remaining_length = self.total_length
        super().save(*args, **kwargs)

    @property
    def assigned_length(self):
        """Total cloth already assigned across all Production records."""
        from django.db.models import Sum
        result = self.productions.aggregate(total=Sum("length_assigned"))
        return result["total"] or 0


# ---------------------------------------------------------------------------
# THAAN PURCHASE
# ---------------------------------------------------------------------------

class ThaanPurchase(models.Model):
    """
    Tracks the purchase invoice and payment for a Thaan.
    Kept separate from Thaan so financial records are isolated.

    UPDATE 10: related_name="purchases" on both Thaan and Brand FKs.
    UPDATE 8:  CheckConstraint ensures price_paid >= 0.
    """

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID    = "paid"

    PAYMENT_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID,    "Paid"),
    ]

    purchase_id    = models.AutoField(primary_key=True)
    thaan          = models.ForeignKey(
        Thaan,
        on_delete=models.PROTECT,
        related_name="purchases",
        help_text="Which thaan this purchase record belongs to."
    )
    brand          = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="purchases",
        help_text="Denormalised brand for fast filtering (must match thaan.brand)."
    )
    invoice_number = models.CharField(
        max_length=100,
        unique=True,
        help_text="Supplier invoice number — must be unique."
    )
    purchase_date  = models.DateField(default=timezone.now)
    price_paid     = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Amount paid or to be paid for this thaan."
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_CHOICES,
        default=PAYMENT_PENDING
    )

    class Meta:
        db_table            = "thaan_purchase"
        ordering            = ["-purchase_date"]
        verbose_name        = "Thaan Purchase"
        verbose_name_plural = "Thaan Purchases"
        # UPDATE 8
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_paid__gte=0),
                name="chk_purchase_price_paid_non_negative",
            ),
        ]

    def __str__(self):
        return (
            f"Purchase #{self.purchase_id} — "
            f"Thaan #{self.thaan_id} / "
            f"Invoice {self.invoice_number}"
        )