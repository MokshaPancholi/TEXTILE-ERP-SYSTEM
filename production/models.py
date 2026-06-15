"""
production/models.py
====================
Handles karigar management, cloth assignment, and production tracking.
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from inventory.models import Thaan


# ---------------------------------------------------------------------------
# KARIGAR
# ---------------------------------------------------------------------------

class Karigar(models.Model):
    karigar_id = models.AutoField(primary_key=True)
    name       = models.CharField(max_length=150)

    class Meta:
        db_table            = "karigar"
        ordering            = ["name"]
        verbose_name        = "Karigar"
        verbose_name_plural = "Karigars"

    def __str__(self):
        return f"{self.name} (ID: {self.karigar_id})"

    @property
    def total_paid(self):
        from django.db.models import Sum
        result = self.payments.aggregate(total=Sum("amount_paid"))
        return result["total"] or 0


# ---------------------------------------------------------------------------
# KARIGAR PAYMENT
# ---------------------------------------------------------------------------

class KarigarPayment(models.Model):
    PAYMENT_PENDING = "pending"
    PAYMENT_PARTIAL = "partial"
    PAYMENT_PAID    = "paid"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PARTIAL, "Partial"),
        (PAYMENT_PAID,    "Paid"),
    ]

    payment_id     = models.AutoField(primary_key=True)
    karigar        = models.ForeignKey(
        Karigar,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_date   = models.DateField(default=timezone.now)
    amount_paid    = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
    )
    remarks = models.TextField(blank=True, default="")

    class Meta:
        db_table            = "karigar_payment"
        ordering            = ["-payment_date"]
        verbose_name        = "Karigar Payment"
        verbose_name_plural = "Karigar Payments"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_paid__gte=0),
                name="chk_karigar_payment_amount_non_negative",
            ),
        ]

    def __str__(self):
        return (
            f"Payment #{self.payment_id} — "
            f"{self.karigar.name} — "
            f"₹{self.amount_paid} [{self.get_payment_status_display()}] "
            f"on {self.payment_date}"
        )

    @property
    def karigar_total_paid(self):
        from django.db.models import Sum
        result = self.karigar.payments.aggregate(total=Sum("amount_paid"))
        return result["total"] or 0

    @property
    def karigar_total_labour_due(self):
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        result = self.karigar.productions.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("actual_kurtas_made") * F("price_per_piece"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        )
        return result["total"] or 0

    @property
    def karigar_balance_due(self):
        return self.karigar_total_labour_due - self.karigar_total_paid


# ---------------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------------

class Production(models.Model):
    STATUS_PENDING   = "pending"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING,   "Pending"),
        (STATUS_COMPLETED, "Completed"),
    ]

    production_id = models.AutoField(primary_key=True)

    thaan = models.ForeignKey(
        Thaan,
        on_delete=models.PROTECT,
        related_name="productions",
    )
    karigar = models.ForeignKey(
        Karigar,
        on_delete=models.PROTECT,
        related_name="productions",
    )
    length_assigned = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Cloth length handed over to this karigar in metres.",
    )
    planned_kurtas = models.PositiveIntegerField(
        help_text="Number of kurtas expected from this assignment.",
    )
    actual_kurtas_made = models.PositiveIntegerField(
        default=0,
        help_text="Kurtas actually delivered by the karigar so far.",
    )
    price_per_piece = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Labour cost per kurta (NOT the selling price).",
    )
    date_assigned = models.DateField(
        default=timezone.now,
    )
    remaining_length_after_making = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text="Unused cloth returned after production.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    class Meta:
        db_table            = "production"
        ordering            = ["-date_assigned"]
        verbose_name        = "Production Assignment"
        verbose_name_plural = "Production Assignments"
        indexes = [
            models.Index(fields=["thaan"],         name="idx_prod_thaan"),
            models.Index(fields=["karigar"],       name="idx_prod_karigar"),
            models.Index(fields=["status"],        name="idx_prod_status"),
            models.Index(fields=["date_assigned"], name="idx_prod_date_assigned"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(length_assigned__gt=0),
                name="chk_prod_length_assigned_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_kurtas__gt=0),
                name="chk_prod_planned_kurtas_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(actual_kurtas_made__gte=0),
                name="chk_prod_actual_kurtas_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(price_per_piece__gte=0),
                name="chk_prod_price_per_piece_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(remaining_length_after_making__gte=0),
                name="chk_prod_remaining_length_non_negative",
            ),
        ]

    def __str__(self):
        return (
            f"Production #{self.production_id} — "
            f"Thaan #{self.thaan_id} / "
            f"Karigar: {self.karigar.name}"
        )

    # ------------------------------------------------------------------
    # BUG FIX: Guard all properties against None (new unsaved objects
    # have None field values when the admin Add form first renders)
    # ------------------------------------------------------------------

    @property
    def remaining_kurtas(self):
        """Kurtas still to be produced. Returns None if object not saved yet."""
        if self.planned_kurtas is None or self.actual_kurtas_made is None:
            return None
        return max(self.planned_kurtas - self.actual_kurtas_made, 0)

    @property
    def labour_cost_total(self):
        """Total labour cost. Returns None if object not saved yet."""
        if self.actual_kurtas_made is None or self.price_per_piece is None:
            return None
        return self.actual_kurtas_made * self.price_per_piece

    # ------------------------------------------------------------------
    # Validation: total assigned length must not exceed thaan.total_length
    # ------------------------------------------------------------------

    def clean(self):
        from django.db.models import Sum

        if not self.thaan_id or self.length_assigned is None:
            return

        existing_qs = Production.objects.filter(thaan_id=self.thaan_id)
        if self.pk:
            existing_qs = existing_qs.exclude(pk=self.pk)

        existing_total = (
            existing_qs.aggregate(total=Sum("length_assigned"))["total"] or 0
        )
        new_total = existing_total + self.length_assigned

        if new_total > self.thaan.total_length:
            available = self.thaan.total_length - existing_total
            raise ValidationError({
                "length_assigned": (
                    f"Cannot assign {self.length_assigned}m. "
                    f"Thaan #{self.thaan_id} only has {available}m available "
                    f"(total: {self.thaan.total_length}m, "
                    f"already assigned: {existing_total}m)."
                )
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)