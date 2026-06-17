"""
sales/urls.py
Stock management, billing, sales orders, sales reports
"""
from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    # Stock management
    path("stock/add/", views.add_stock, name="add_stock"),
    path("stock/list/", views.list_stock, name="list_stock"),

    # Bills & Orders
    path("bills/create/", views.create_bill, name="create_bill"),
    path("bills/<int:bill_no>/", views.bill_detail, name="bill_detail"),
    path("bills/list/", views.list_bills, name="list_bills"),
    path("bills/items/add/", views.add_bill_item, name="add_bill_item"),

    path('bills/<int:bill_no>/pdf/', views.generate_bill_pdf, name='generate_bill_pdf'),

    # Reports
    path("reports/stock/", views.stock_report, name="stock_report"),
    path("reports/sales/", views.sales_report, name="sales_report"),
    path("customers/<str:customer_name>/history/", views.customer_sales_history, name="customer_history"),
]