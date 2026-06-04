"""
production/models.py
====================
Handles karigar management, cloth assignment, and production tracking.

UPDATES APPLIED:
    - UPDATE 3:  Removed Production.total_length (redundant — lives on Thaan)
    - UPDATE 4:  KarigarPayment.payment_status added (Pending/Partial/Paid)
                 KarigarPayment.total_paid_to_karigar property added
    - UPDATE 5:  Production.clean() validates total assigned length <= thaan.total_length
    - UPDATE 8:  CheckConstraints on Production and KarigarPayment
    - UPDATE 9:  Indexes on Production.Meta
    - UPDATE 10: FK related_names reviewed and confirmed
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
    """
    A Karigar is a tailor / worker who stitches kurtas from cloth.
    Karigars can be added, updated, or removed dynamically at runtime.
    """

    karigar_id = models.AutoField(primary_key=True)
    name       = models.CharField(
        max_length=150,
        help_text="Full name of the karigar."
    )

    class Meta:
        db_table            = "karigar"
        ordering            = ["name"]
        verbose_name        = "Karigar"
        verbose_name_plural = "Karigars"

    def __str__(self):
        return f"{self.name} (ID: {self.karigar_id})"

    @property
    def total_paid(self):
        """Sum of all payments made to this karigar across all transactions."""
        from django.db.models import Sum
        result = self.payments.aggregate(total=Sum("amount_paid"))
        return result["total"] or 0


# ---------------------------------------------------------------------------
# KARIGAR PAYMENT
# ---------------------------------------------------------------------------

class KarigarPayment(models.Model):
    """
    Tracks individual payment transactions made to a karigar.
    One karigar can receive many payments over time.

    UPDATE 4:
        - Added payment_status field with choices: Pending / Partial / Paid
        - Added total_due property (calculates labour owed from productions)
        - Added balance_due property (total_due - amount_paid for this record)
    UPDATE 8:
        - CheckConstraint: amount_paid >= 0
    """

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
        on_delete=models.PROTECT,       # preserve payment history even if karigar is removed
        related_name="payments",
        help_text="Karigar who received this payment."
    )
    payment_date   = models.DateField(default=timezone.now)
    amount_paid    = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Amount paid in this transaction."
    )
    # UPDATE 4: payment_status tracks settlement stage of this payment record
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
        help_text=(
            "Pending = not yet paid; "
            "Partial = partially paid; "
            "Paid = fully settled."
        )
    )
    remarks        = models.TextField(
        blank=True,
        default="",
        help_text="Optional notes (advance, final settlement, partial, etc.)."
    )

    class Meta:
        db_table            = "karigar_payment"
        ordering            = ["-payment_date"]
        verbose_name        = "Karigar Payment"
        verbose_name_plural = "Karigar Payments"
        # UPDATE 8
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

    # ------------------------------------------------------------------
    # UPDATE 4: Calculated properties
    # ------------------------------------------------------------------

    @property
    def karigar_total_paid(self):
        """
        Lifetime total paid to this karigar across ALL payment records.
        Useful for payment summary screens.
        """
        from django.db.models import Sum
        result = self.karigar.payments.aggregate(total=Sum("amount_paid"))
        return result["total"] or 0

    @property
    def karigar_total_labour_due(self):
        """
        Total labour cost owed to this karigar based on actual kurtas made.
        Calculated as: SUM(actual_kurtas_made × price_per_piece) across all productions.
        """
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
        """
        Outstanding balance = total labour due − total already paid.
        A positive value means karigar is still owed money.
        """
        return self.karigar_total_labour_due - self.karigar_total_paid


# ---------------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------------

class Production(models.Model):
    """
    Represents a single cloth assignment from a Thaan to a Karigar.

    One Thaan can have MULTIPLE Production records (split assignments).
    Example:
        Thaan 12201 (20m total)
          → Production A: Karigar A gets 10m
          → Production B: Karigar B gets 10m

    UPDATE 3: total_length REMOVED — it was redundant since Thaan already
              stores total_length. Production only needs length_assigned.

    UPDATE 5: clean() validates that the SUM of all length_assigned for a
              Thaan never exceeds thaan.total_length.

    UPDATE 8: CheckConstraints on length_assigned, planned_kurtas,
              actual_kurtas_made, price_per_piece.

    UPDATE 9: Indexes on karigar, thaan, status, date_assigned.
    """

    STATUS_PENDING   = "pending"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING,   "Pending"),
        (STATUS_COMPLETED, "Completed"),
    ]

    production_id = models.AutoField(primary_key=True)

    # UPDATE 10: related_name="productions" on both Thaan and Karigar FKs
    thaan = models.ForeignKey(
        Thaan,
        on_delete=models.PROTECT,
        related_name="productions",
        help_text="Thaan from which cloth was taken for this assignment."
    )
    karigar = models.ForeignKey(
        Karigar,
        on_delete=models.PROTECT,
        related_name="productions",
        help_text="Karigar assigned to stitch kurtas for this assignment."
    )

    # ---- Cloth tracking --------------------------------------------------
    # UPDATE 3: total_length field REMOVED here.
    # Use production.thaan.total_length when the full thaan length is needed.
    length_assigned = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Cloth length handed over to this karigar in metres."
    )

    # ---- Kurta tracking --------------------------------------------------
    planned_kurtas = models.PositiveIntegerField(
        help_text="Number of kurtas expected from this assignment."
    )
    actual_kurtas_made = models.PositiveIntegerField(
        default=0,
        help_text="Kurtas actually delivered by the karigar so far."
    )

    # ---- Financials -------------------------------------------------------
    price_per_piece = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Labour cost per kurta paid to karigar. NOT the selling price."
    )

    # ---- Misc -------------------------------------------------------------
    date_assigned = models.DateField(
        default=timezone.now,
        help_text="Date cloth was physically handed over to karigar."
    )
    remaining_length_after_making = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text="Cloth returned unused after production (waste tracking)."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    class Meta:
        db_table            = "production"
        ordering            = ["-date_assigned"]
        verbose_name        = "Production Assignment"
        verbose_name_plural = "Production Assignments"
        # UPDATE 9: Indexes for filtering and searching
        indexes = [
            models.Index(fields=["thaan"],         name="idx_prod_thaan"),
            models.Index(fields=["karigar"],       name="idx_prod_karigar"),
            models.Index(fields=["status"],        name="idx_prod_status"),
            models.Index(fields=["date_assigned"], name="idx_prod_date_assigned"),
        ]
        # UPDATE 8: DB-level constraints — enforced by PostgreSQL directly
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
    # UPDATE 5: Business rule validation
    # ------------------------------------------------------------------

    def clean(self):
        """
        Validates that total cloth assigned to all productions for this Thaan
        does not exceed the Thaan's total_length.

        Business Rule:
            SUM(length_assigned for all Production records of this Thaan)
            must not exceed Thaan.total_length.

        Example:
            Thaan total_length = 20m
            Existing: 10m + 10m = 20m  → OK
            New attempt: + 5m          → ValidationError raised here
        """
        from django.db.models import Sum

        if not self.thaan_id:
            return  # FK not set yet — skip (form validation handles required)

        # Sum of ALL other productions for this thaan (excluding self on edit)
        existing_qs = Production.objects.filter(thaan_id=self.thaan_id)
        if self.pk:
            existing_qs = existing_qs.exclude(pk=self.pk)

        existing_total = (
            existing_qs.aggregate(total=Sum("length_assigned"))["total"] or 0
        )

        if self.length_assigned is None:
            return  # field-level validator will handle None

        new_total = existing_total + self.length_assigned

        if new_total > self.thaan.total_length:
            available = self.thaan.total_length - existing_total
            raise ValidationError({
                "length_assigned": (
                    f"Cannot assign {self.length_assigned}m. "
                    f"Thaan #{self.thaan_id} has only {available}m available "
                    f"(total: {self.thaan.total_length}m, "
                    f"already assigned: {existing_total}m)."
                )
            })

    def save(self, *args, **kwargs):
        """Run full_clean (which calls clean) before every save."""
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Calculated properties (never stored)
    # ------------------------------------------------------------------

    @property
    def remaining_kurtas(self):
        """
        Kurtas still to be produced by the karigar.
        Returns 0 if karigar has over-delivered (never negative).
        """
        return max(self.planned_kurtas - self.actual_kurtas_made, 0)

    @property
    def labour_cost_total(self):
        """Total labour cost = actual kurtas made × price per piece."""
        return self.actual_kurtas_made * self.price_per_piece