"""
sales/views.py
==============
Backend logic for sales workflow: Stock management, billing, order fulfillment.
No frontend — pure business automation.
Signals auto-update stock.sold_quantity on every BillItem operation.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, F
from decimal import Decimal
from .models import KurtaStock, Bill, BillItem
from inventory.models import Thaan


# ---------------------------------------------------------------------------
# STOCK MANAGEMENT
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def add_stock(request):
    """
    Add finished kurtas to stock.
    Expected: thaan_no, size, quantity
    Creates or updates KurtaStock record.
    """
    if not request.user.is_billing_staff:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            thaan = Thaan.objects.get(thaan_no=int(request.POST.get("thaan_no")))
            size = int(request.POST.get("size"))
            quantity = int(request.POST.get("quantity"))

            stock, created = KurtaStock.objects.get_or_create(
                thaan=thaan,
                size=size,
                defaults={"produced_quantity": 0, "sold_quantity": 0}
            )

            stock.produced_quantity += quantity
            stock.save()

        return JsonResponse({
            "status": "success",
            "stock_id": stock.stock_id,
            "produced_quantity": stock.produced_quantity,
            "available_stock": stock.stock_quantity,
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def list_stock(request):
    """
    List all stock with availability.
    Query params: thaan_no (optional), size (optional), low_stock (boolean)
    """
    query = KurtaStock.objects.select_related("thaan").all()

    thaan_no = request.GET.get("thaan_no")
    if thaan_no:
        query = query.filter(thaan_id=int(thaan_no))

    size = request.GET.get("size")
    if size:
        query = query.filter(size=int(size))

    # Low stock filter (< 5 units)
    low_stock = request.GET.get("low_stock")

    stock_list = []
    for s in query:
        if low_stock and s.stock_quantity >= 5:
            continue

        stock_list.append({
            "stock_id": s.stock_id,
            "thaan_no": s.thaan_id,
            "size": s.size,
            "produced_quantity": s.produced_quantity,
            "sold_quantity": s.sold_quantity,
            "available_stock": s.stock_quantity,
            "is_out_of_stock": s.is_out_of_stock,
        })

    return JsonResponse({"status": "success", "stock": stock_list})


@require_http_methods(["GET"])
@login_required
def stock_report(request):
    """
    Generate stock availability report.
    Returns: total produced, total sold, total available by thaan/size
    """
    report_data = []

    for stock in KurtaStock.objects.select_related("thaan"):
        report_data.append({
            "thaan_no": stock.thaan_id,
            "size": stock.size,
            "produced": stock.produced_quantity,
            "sold": stock.sold_quantity,
            "available": stock.stock_quantity,
            "status": "OUT OF STOCK" if stock.is_out_of_stock else ("LOW" if stock.stock_quantity <= 5 else "OK"),
        })

    return JsonResponse({"status": "success", "report": report_data})


# ---------------------------------------------------------------------------
# BILLING & SALES ORDERS
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@login_required
def create_bill(request):
    """
    Create a new bill (sales order).
    Expected: customer_name, bill_date
    Returns: bill_no for adding line items
    """
    if not request.user.is_billing_staff:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            bill = Bill.objects.create(
                customer_name=request.POST.get("customer_name"),
                bill_date=request.POST.get("bill_date"),
            )

        return JsonResponse({
            "status": "success",
            "bill_no": bill.bill_no,
            "customer_name": bill.customer_name,
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def add_bill_item(request):
    """
    Add a line item to a bill.
    Expected: bill_no, stock_id, quantity, price
    Validates: quantity <= available stock
    Signals auto-update sold_quantity
    """
    if not request.user.is_billing_staff:
        return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

    try:
        with transaction.atomic():
            bill = Bill.objects.get(bill_no=int(request.POST.get("bill_no")))
            stock = KurtaStock.objects.get(stock_id=int(request.POST.get("stock_id")))
            quantity = int(request.POST.get("quantity"))
            price = Decimal(request.POST.get("price"))

            # Validate stock availability
            if quantity > stock.stock_quantity:
                return JsonResponse({
                    "status": "error",
                    "message": f"Only {stock.stock_quantity} available. Requested {quantity}"
                }, status=400)

            bill_item = BillItem.objects.create(
                bill=bill,
                stock=stock,
                quantity=quantity,
                price=price,
            )
            # Signals auto-update stock.sold_quantity

        return JsonResponse({
            "status": "success",
            "item_id": bill_item.item_id,
            "subtotal": float(bill_item.subtotal),
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def bill_detail(request, bill_no):
    """Get detailed bill with all line items."""
    try:
        bill = Bill.objects.get(bill_no=bill_no)
        items = bill.items.select_related("stock__thaan").values(
            "item_id", "stock__size", "quantity", "price"
        )

        return JsonResponse({
            "status": "success",
            "bill": {
                "bill_no": bill.bill_no,
                "customer_name": bill.customer_name,
                "bill_date": bill.bill_date.isoformat(),
                "total_quantity": bill.total_quantity,
                "total_price": float(bill.total_price),
            },
            "items": list(items),
        })
    except Bill.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Bill not found"}, status=404)


@require_http_methods(["GET"])
@login_required
def list_bills(request):
    """List all bills with summary."""
    bills = []

    for bill in Bill.objects.all().order_by("-bill_date")[:100]:
        bills.append({
            "bill_no": bill.bill_no,
            "customer_name": bill.customer_name,
            "bill_date": bill.bill_date.isoformat(),
            "total_quantity": bill.total_quantity,
            "total_price": float(bill.total_price),
            "line_items_count": bill.items.count(),
        })

    return JsonResponse({"status": "success", "bills": bills})


# ---------------------------------------------------------------------------
# SALES REPORTS
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
@login_required
def sales_report(request):
    """
    Generate sales report.
    Returns: total bills, total quantity sold, total revenue
    """
    total_bills = Bill.objects.count()
    total_quantity = BillItem.objects.aggregate(Sum("quantity"))["quantity__sum"] or 0
    total_revenue = BillItem.objects.aggregate(
        total=Sum(F("quantity") * F("price"))
    )["total"] or Decimal("0")

    return JsonResponse({
        "status": "success",
        "total_bills": total_bills,
        "total_quantity_sold": total_quantity,
        "total_revenue": float(total_revenue),
    })


@require_http_methods(["GET"])
@login_required
def customer_sales_history(request, customer_name):
    """Get sales history for a specific customer."""
    bills = Bill.objects.filter(customer_name__icontains=customer_name).values(
        "bill_no", "bill_date", "items__quantity", "items__price"
    )

    total = BillItem.objects.filter(bill__customer_name__icontains=customer_name).aggregate(
        total=Sum(F("quantity") * F("price"))
    )["total"] or Decimal("0")

    return JsonResponse({
        "status": "success",
        "customer": customer_name,
        "bills": list(bills),
        "total_spent": float(total),
    })