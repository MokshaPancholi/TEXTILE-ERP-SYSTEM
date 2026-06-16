"""
production/urls.py
Karigars, production assignments, payments, production reports
"""
from django.urls import path
from . import views

app_name = "production"

urlpatterns = [
    # Karigars
    path("karigars/create/", views.create_karigar, name="create_karigar"),
    path("karigars/list/", views.list_karigars, name="list_karigars"),

    # Production assignments
    path("create/", views.create_production, name="create_production"),
    path("list/", views.list_productions, name="list_productions"),
    path("<int:production_id>/update-kurtas/", views.update_production_kurtas, name="update_kurtas"),
    path("<int:production_id>/complete/", views.mark_production_complete, name="complete_production"),

    # Karigar payments
    path("payments/create/", views.create_payment, name="create_payment"),
    path("karigars/<int:karigar_id>/balance/", views.karigar_balance, name="karigar_balance"),

    # Reports
    path("reports/production/", views.production_report, name="production_report"),
]