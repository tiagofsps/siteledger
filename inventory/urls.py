from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("items/", views.ItemListView.as_view(), name="item_list"),
    path("items/new/", views.ItemCreateView.as_view(), name="item_create"),
    path("items/<int:pk>/", views.ItemDetailView.as_view(), name="item_detail"),
    path(
        "items/<int:pk>/edit/",
        views.ItemUpdateView.as_view(),
        name="item_update",
    ),
    path("locations/", views.LocationListView.as_view(), name="location_list"),
    path("movements/", views.MovementListView.as_view(), name="movement_list"),
    path(
        "movements/new/initial/",
        views.initial_entry_create,
        name="initial_entry_create",
    ),
    path(
        "movements/new/transfer/",
        views.transfer_create,
        name="transfer_create",
    ),
    path(
        "movements/new/return/",
        views.return_to_warehouse_create,
        name="return_to_warehouse",
    ),
    path(
        "movements/new/adjustment-in/",
        views.adjustment_in_create,
        name="adjustment_in_create",
    ),
    path(
        "movements/new/adjustment-out/",
        views.adjustment_out_create,
        name="adjustment_out_create",
    ),
    path(
        "movements/<int:pk>/",
        views.MovementDetailView.as_view(),
        name="movement_detail",
    ),
    path(
        "movements/<int:pk>/cancel/",
        views.movement_cancel,
        name="movement_cancel",
    ),
]
