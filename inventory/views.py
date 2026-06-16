"""
inventory/views.py
==================
Backend logic for inventory management: Brands, Thaans, Purchase tracking.
No frontend templates — pure business logic.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from .models import Brand, Thaan, ThaanPurchase


# ---------------------------------------------------------------------------
# BRAND MANAGEMENT
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def create_brand(request):
    """Create a new brand/supplier."""
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        brand_name = request.POST.get("brand_name")
        brand = Brand.objects.create(brand_name=brand_name)
        return JsonResponse({"status": "success", "brand_id": brand.brand_id, "brand_name": brand.brand_name})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def list_brands(request):
    """List all brands with thaan count."""
    brands = Brand.objects.annotate(thaan_count=Sum("thaans")).values(
        "brand_id", "brand_name", "thaan_count"
    )
    return JsonResponse({"status": "success", "brands": list(brands)})


# ---------------------------------------------------------------------------
# THAAN MANAGEMENT
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def create_thaan(request):
    """
    Create a new Thaan (cloth roll).
    Expected: thaan_no, brand_id, total_length, date_received
    """
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            thaan = Thaan.objects.create(
                thaan_no=int(request.POST.get("thaan_no")),
                brand_id=int(request.POST.get("brand_id")),
                total_length=Decimal(request.POST.get("total_length")),
                remaining_length=Decimal(request.POST.get("total_length")),
                date_received=request.POST.get("date_received"),
                status=Thaan.STATUS_ACTIVE,
            )

        return JsonResponse({
            "status": "success",
            "thaan_no": thaan.thaan_no,
            "brand": str(thaan.brand),
            "total_length": float(thaan.total_length),
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def list_thaans(request):
    """
    List all thaans with their status and remaining cloth.
    Query params: brand_id (optional), status (optional)
    """
    query = Thaan.objects.select_related("brand")

    brand_id = request.GET.get("brand_id")
    if brand_id:
        query = query.filter(brand_id=brand_id)

    status = request.GET.get("status")
    if status:
        query = query.filter(status=status)

    thaans = query.values(
        "thaan_no", "brand__brand_name", "total_length",
        "remaining_length", "status", "date_received"
    )
    return JsonResponse({
        "status": "success",
        "thaans": list(thaans),
        "total_count": query.count(),
    })


@require_http_methods(["GET"])
@login_required
def thaan_detail(request, thaan_no):
    """Get detailed view of a single thaan with production assignments."""
    try:
        thaan = Thaan.objects.get(thaan_no=thaan_no)
        productions = thaan.productions.select_related("karigar").values(
            "production_id", "karigar__name", "length_assigned",
            "planned_kurtas", "actual_kurtas_made", "status"
        )

        return JsonResponse({
            "status": "success",
            "thaan": {
                "thaan_no": thaan.thaan_no,
                "brand": str(thaan.brand),
                "total_length": float(thaan.total_length),
                "remaining_length": float(thaan.remaining_length),
                "status": thaan.status,
                "date_received": thaan.date_received.isoformat(),
            },
            "productions": list(productions),
        })
    except Thaan.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Thaan not found"}, status=404)


# ---------------------------------------------------------------------------
# PURCHASE TRACKING
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def create_purchase(request):
    """
    Record a purchase/invoice for a thaan.
    Expected: thaan_no, invoice_number, purchase_date, price_paid
    """
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            thaan = Thaan.objects.get(thaan_no=int(request.POST.get("thaan_no")))
            purchase = ThaanPurchase.objects.create(
                thaan=thaan,
                brand=thaan.brand,
                invoice_number=request.POST.get("invoice_number"),
                purchase_date=request.POST.get("purchase_date"),
                price_paid=Decimal(request.POST.get("price_paid")),
                payment_status=ThaanPurchase.PAYMENT_PENDING,
            )

        return JsonResponse({
            "status": "success",
            "purchase_id": purchase.purchase_id,
            "thaan_no": thaan.thaan_no,
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def mark_purchase_paid(request, purchase_id):
    """Mark a purchase invoice as paid."""
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        purchase = ThaanPurchase.objects.get(purchase_id=purchase_id)
        purchase.payment_status = ThaanPurchase.PAYMENT_PAID
        purchase.save()

        return JsonResponse({"status": "success", "message": "Marked as paid"})
    except ThaanPurchase.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Purchase not found"}, status=404)


@require_http_methods(["GET"])
@login_required
def inventory_report(request):
    """
    Generate inventory report.
    Returns: total cloth received, assigned, remaining by brand
    """
    brands = Brand.objects.prefetch_related("thaans").all()
    report = []

    for brand in brands:
        thaans = brand.thaans.all()
        total_received = sum(float(t.total_length) for t in thaans)
        total_assigned = sum(float(t.assigned_length) for t in thaans)
        total_remaining = sum(float(t.remaining_length) for t in thaans)

        report.append({
            "brand_id": brand.brand_id,
            "brand_name": brand.brand_name,
            "total_received": total_received,
            "total_assigned": total_assigned,
            "total_remaining": total_remaining,
            "thaan_count": thaans.count(),
        })

    return JsonResponse({"status": "success", "report": report})