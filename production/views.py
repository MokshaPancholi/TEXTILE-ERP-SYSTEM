"""
production/views.py
===================
Backend logic for production workflow: Karigars, assignments, production tracking.
No frontend — pure business automation.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, F
from decimal import Decimal
from .models import Karigar, Production, KarigarPayment
from inventory.models import Thaan


# ---------------------------------------------------------------------------
# KARIGAR MANAGEMENT
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def create_karigar(request):
    """Create a new karigar (tailor)."""
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        karigar = Karigar.objects.create(name=request.POST.get("name"))
        return JsonResponse({"status": "success", "karigar_id": karigar.karigar_id, "name": karigar.name})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def list_karigars(request):
    """List all karigars with assignment count."""
    karigars = []
    for k in Karigar.objects.all():
        karigars.append({
            "karigar_id": k.karigar_id,
            "name": k.name,
            "total_assignments": k.productions.count(),
            "total_paid": float(k.total_paid),
            "pending_payments": k.productions.filter(status=Production.STATUS_PENDING).count(),
        })
    return JsonResponse({"status": "success", "karigars": karigars})


# ---------------------------------------------------------------------------
# PRODUCTION ASSIGNMENT
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def create_production(request):
    """
    Assign cloth to a karigar for production.
    Expected: thaan_no, karigar_id, length_assigned, planned_kurtas, price_per_piece
    Validates: total assigned length cannot exceed thaan.total_length
    """
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            thaan = Thaan.objects.get(thaan_no=int(request.POST.get("thaan_no")))
            karigar = Karigar.objects.get(karigar_id=int(request.POST.get("karigar_id")))

            length_assigned = Decimal(request.POST.get("length_assigned"))

            # Validate length doesn't exceed remaining
            existing_assigned = (
                    Production.objects
                    .filter(thaan=thaan)
                    .aggregate(total=Sum("length_assigned"))["total"] or 0
            )

            if existing_assigned + length_assigned > thaan.total_length:
                available = thaan.total_length - existing_assigned
                return JsonResponse({
                    "status": "error",
                    "message": f"Only {available}m available. Requested {length_assigned}m"
                }, status=400)

            production = Production.objects.create(
                thaan=thaan,
                karigar=karigar,
                length_assigned=length_assigned,
                planned_kurtas=int(request.POST.get("planned_kurtas")),
                price_per_piece=Decimal(request.POST.get("price_per_piece")),
                status=Production.STATUS_PENDING,
            )

            # Signals auto-update thaan.remaining_length

        return JsonResponse({
            "status": "success",
            "production_id": production.production_id,
            "thaan_no": thaan.thaan_no,
            "karigar": karigar.name,
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def update_production_kurtas(request, production_id):
    """
    Update the actual kurtas made by a karigar.
    Expected: actual_kurtas_made
    """
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        production = Production.objects.get(production_id=production_id)
        actual = int(request.POST.get("actual_kurtas_made"))

        production.actual_kurtas_made = actual
        production.save()

        return JsonResponse({
            "status": "success",
            "production_id": production.production_id,
            "actual_kurtas_made": production.actual_kurtas_made,
            "remaining_kurtas": production.remaining_kurtas,
        })
    except Production.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Production not found"}, status=404)


@require_http_methods(["POST"])
@login_required
def mark_production_complete(request, production_id):
    """Mark a production assignment as completed."""
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        production = Production.objects.get(production_id=production_id)
        production.status = Production.STATUS_COMPLETED
        production.save()

        return JsonResponse({"status": "success", "message": "Production marked complete"})
    except Production.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Production not found"}, status=404)


@require_http_methods(["GET"])
@login_required
def list_productions(request):
    """List all production assignments with optional filters."""
    query = Production.objects.select_related("thaan", "karigar")

    # Filter by status
    status = request.GET.get("status")
    if status:
        query = query.filter(status=status)

    # Filter by karigar
    karigar_id = request.GET.get("karigar_id")
    if karigar_id:
        query = query.filter(karigar_id=karigar_id)

    productions = []
    for p in query:
        productions.append({
            "production_id": p.production_id,
            "thaan_no": p.thaan_id,
            "karigar": p.karigar.name,
            "length_assigned": float(p.length_assigned),
            "planned_kurtas": p.planned_kurtas,
            "actual_kurtas_made": p.actual_kurtas_made,
            "remaining_kurtas": p.remaining_kurtas,
            "status": p.status,
            "labour_cost_total": float(p.labour_cost_total) if p.labour_cost_total else 0,
        })

    return JsonResponse({"status": "success", "productions": productions})


# ---------------------------------------------------------------------------
# KARIGAR PAYMENTS
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def create_payment(request):
    """
    Record a payment to a karigar.
    Expected: karigar_id, amount_paid, payment_status
    """
    if not request.user.is_manager:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            karigar = Karigar.objects.get(karigar_id=int(request.POST.get("karigar_id")))

            payment = KarigarPayment.objects.create(
                karigar=karigar,
                amount_paid=Decimal(request.POST.get("amount_paid")),
                payment_status=request.POST.get("payment_status", KarigarPayment.PAYMENT_PENDING),
                remarks=request.POST.get("remarks", ""),
            )

        return JsonResponse({
            "status": "success",
            "payment_id": payment.payment_id,
            "karigar": karigar.name,
            "amount_paid": float(payment.amount_paid),
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def karigar_balance(request, karigar_id):
    """Get karigar payment status and balance due."""
    try:
        karigar = Karigar.objects.get(karigar_id=karigar_id)

        # Calculate total labour owed
        total_labour_due = (
                karigar.productions.aggregate(
                    total=Sum(F("actual_kurtas_made") * F("price_per_piece"))
                )["total"] or Decimal("0")
        )

        # Calculate total paid
        total_paid = (
                karigar.payments.aggregate(
                    total=Sum("amount_paid")
                )["total"] or Decimal("0")
        )

        balance_due = float(total_labour_due - total_paid)

        return JsonResponse({
            "status": "success",
            "karigar_id": karigar_id,
            "karigar_name": karigar.name,
            "total_labour_due": float(total_labour_due),
            "total_paid": float(total_paid),
            "balance_due": balance_due,
        })
    except Karigar.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Karigar not found"}, status=404)


@require_http_methods(["GET"])
@login_required
def production_report(request):
    """
    Production status report.
    Shows: pending assignments, completed assignments, total labour cost
    """
    pending = Production.objects.filter(status=Production.STATUS_PENDING).count()
    completed = Production.objects.filter(status=Production.STATUS_COMPLETED).count()

    total_labour_cost = (
            Production.objects.aggregate(
                total=Sum(F("actual_kurtas_made") * F("price_per_piece"))
            )["total"] or Decimal("0")
    )

    return JsonResponse({
        "status": "success",
        "pending_assignments": pending,
        "completed_assignments": completed,
        "total_labour_cost": float(total_labour_cost),
    })