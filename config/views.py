from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from inventory.models import Item, StockMovement
from projects.models import Project
from purchases.models import Purchase, Supplier


@require_GET
def search(request):
    query = request.GET.get("q", "").strip()[:200]
    is_htmx = request.headers.get("HX-Request") == "true"

    if not query:
        if is_htmx:
            return HttpResponse("")
        return render(
            request,
            "search/search_results.html",
            {"query": ""},
        )

    limit = 5 if is_htmx else 20
    user = request.user

    projects = Project.objects.none()
    purchases = Purchase.objects.none()
    suppliers = Supplier.objects.none()
    items = Item.objects.none()
    movements = StockMovement.objects.none()

    if user.has_perm("projects.view_project"):
        projects = Project.objects.filter(
            Q(name__icontains=query)
            | Q(address__icontains=query)
            | Q(description__icontains=query)
        )[:limit]

    if user.has_perm("purchases.view_purchase"):
        purchases = (
            Purchase.objects.select_related("supplier")
            .filter(
                Q(supplier__name__icontains=query)
                | Q(notes__icontains=query)
                | Q(items__description__icontains=query)
                | Q(items__item__name__icontains=query)
            )
            .distinct()[:limit]
        )

    if user.has_perm("purchases.view_supplier"):
        suppliers = Supplier.objects.filter(name__icontains=query)[:limit]

    if user.has_perm("inventory.view_item"):
        items = Item.objects.filter(
            Q(name__icontains=query)
            | Q(unit__icontains=query)
            | Q(description__icontains=query)
        )[:limit]

    if user.has_perm("inventory.view_stockmovement"):
        movements = StockMovement.objects.select_related(
            "item",
            "from_location",
            "to_location",
        ).filter(
            Q(item__name__icontains=query)
            | Q(notes__icontains=query)
            | Q(from_location__name__icontains=query)
            | Q(to_location__name__icontains=query)
        )[:limit]

    context = {
        "query": query,
        "projects": projects,
        "purchases": purchases,
        "suppliers": suppliers,
        "items": items,
        "movements": movements,
    }

    if is_htmx:
        return render(request, "search/partials/results.html", context)

    return render(request, "search/search_results.html", context)
