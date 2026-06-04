"""
sales/signals.py
================
Auto-sync signals — KEPT AS REQUIRED (UPDATE 1).

Signals:
    1. BillItem pre_save  → cache old quantity for delta calculation
    2. BillItem post_save → update KurtaStock.sold_quantity (atomic + select_for_update)
    3. BillItem post_delete → reverse sold_quantity on deletion
    4. Production pre_save  → cache old length_assigned
    5. Production post_save → recalculate Thaan.remaining_length (atomic + select_for_update)

All DB writes use:
    - transaction.atomic()
    - select_for_update() to prevent race conditions in concurrent requests
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction

from sales.models import BillItem
from production.models import Production


# ---------------------------------------------------------------------------
# SIGNAL SET 1 — BillItem → KurtaStock.sold_quantity
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=BillItem)
def cache_old_bill_item_quantity(sender, instance, **kwargs):
    """
    Cache the OLD quantity before a BillItem save so post_save can compute
    the correct delta (handles both CREATE and EDIT of bill items).
    """
    if instance.pk:
        try:
            old = BillItem.objects.get(pk=instance.pk)
            instance._old_quantity = old.quantity
        except BillItem.DoesNotExist:
            instance._old_quantity = 0
    else:
        instance._old_quantity = 0  # brand new record


@receiver(post_save, sender=BillItem)
def update_stock_sold_quantity_on_save(sender, instance, created, **kwargs):
    """
    After a BillItem is saved:
        sold_quantity += (new_quantity - old_quantity)

    Uses select_for_update() to lock the stock row — safe for concurrent billing.
    """
    with transaction.atomic():
        stock = (
            instance.stock.__class__
            .objects.select_for_update()
            .get(pk=instance.stock_id)
        )
        old_qty = getattr(instance, "_old_quantity", 0)
        delta   = instance.quantity - old_qty  # positive on add/increase, negative on decrease

        stock.sold_quantity = max(0, stock.sold_quantity + delta)
        # Use update_fields to skip full_clean (sold_quantity is validated by clean on BillItem)
        stock.sold_quantity = stock.sold_quantity
        KurtaStock = instance.stock.__class__
        KurtaStock.objects.filter(pk=stock.pk).update(sold_quantity=stock.sold_quantity)


@receiver(post_delete, sender=BillItem)
def update_stock_sold_quantity_on_delete(sender, instance, **kwargs):
    """
    If a BillItem is deleted, reverse its sold quantity contribution.
    """
    with transaction.atomic():
        KurtaStock = instance.stock.__class__
        KurtaStock.objects.select_for_update().filter(pk=instance.stock_id).update(
            sold_quantity=models.F("sold_quantity") - instance.quantity
        )


# ---------------------------------------------------------------------------
# SIGNAL SET 2 — Production → Thaan.remaining_length
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=Production)
def cache_old_production_length(sender, instance, **kwargs):
    """Cache the previous length_assigned before an update for delta safety."""
    if instance.pk:
        try:
            old = Production.objects.get(pk=instance.pk)
            instance._old_length_assigned = old.length_assigned
        except Production.DoesNotExist:
            instance._old_length_assigned = 0
    else:
        instance._old_length_assigned = 0


@receiver(post_save, sender=Production)
def update_thaan_remaining_length(sender, instance, created, **kwargs):
    """
    After any Production record is saved, recalculate Thaan.remaining_length.

    Recalculates from scratch (not delta) so that edits are always accurate:
        remaining_length = total_length - SUM(all length_assigned for this thaan)

    Auto-marks Thaan as 'completed' when remaining_length reaches 0.
    """
    from django.db.models import Sum

    with transaction.atomic():
        ThaanModel = instance.thaan.__class__
        thaan = ThaanModel.objects.select_for_update().get(pk=instance.thaan_id)

        assigned_total = (
            Production.objects
            .filter(thaan_id=instance.thaan_id)
            .aggregate(total=Sum("length_assigned"))["total"] or 0
        )

        new_remaining = max(thaan.total_length - assigned_total, 0)
        new_status    = (
            ThaanModel.STATUS_COMPLETED
            if new_remaining == 0
            else ThaanModel.STATUS_ACTIVE
        )

        ThaanModel.objects.filter(pk=thaan.pk).update(
            remaining_length=new_remaining,
            status=new_status,
        )


# Needed for the F() expression in post_delete signal
from django.db import models