from django.urls import path

from . import views

app_name = "purchases"

urlpatterns = [
    path("", views.PurchaseListView.as_view(), name="purchase_list"),
    path("new/", views.purchase_create, name="purchase_create"),
    path("<int:pk>/", views.PurchaseDetailView.as_view(), name="purchase_detail"),
    path("<int:pk>/edit/", views.purchase_update, name="purchase_update"),
    path(
        "<int:pk>/allocations/",
        views.purchase_allocations,
        name="purchase_allocations",
    ),
    path(
        "<int:purchase_pk>/items/<int:item_pk>/allocations/",
        views.item_allocations,
        name="item_allocations",
    ),
    path(
        "items/row/",
        views.purchase_item_row,
        name="purchase_item_row",
    ),
    path("suppliers/", views.SupplierListView.as_view(), name="supplier_list"),
    path("suppliers/new/", views.supplier_create, name="supplier_create"),
    path(
        "suppliers/<int:pk>/edit/",
        views.supplier_update,
        name="supplier_update",
    ),
]
