from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.generic import DetailView, ListView

from inventory.models import Location, StockMovement
from inventory.services import receive_purchase_item

from .forms import (
    PurchaseFilterForm,
    PurchaseForm,
    ReceiptForm,
    SupplierFilterForm,
    SupplierForm,
)
from .formsets import PurchaseItemFormSet
from .models import Purchase, PurchaseItem, Supplier
from .services import recalculate_purchase_total


def _purchase_wizard_step(form, formset):
    if not form.is_bound:
        return 1
    if form.errors:
        return 1
    if not formset.is_valid():
        return 2
    return 1


class SupplierListView(PermissionRequiredMixin, ListView):
    permission_required = "purchases.view_supplier"
    model = Supplier
    paginate_by = 20
    context_object_name = "suppliers"
    template_name = "purchases/supplier_list.html"

    def get_filter_form(self):
        if not hasattr(self, "_filter_form"):
            self._filter_form = SupplierFilterForm(self.request.GET or None)
        return self._filter_form

    def get_queryset(self):
        queryset = super().get_queryset().annotate(
            purchase_count=Count("purchases")
        )
        form = self.get_filter_form()
        if form.is_valid():
            query = form.cleaned_data["q"].strip()
            if query:
                queryset = queryset.filter(name__icontains=query)
        return queryset.order_by("name")

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return ["purchases/partials/supplier_results.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        context["can_add_supplier"] = self.request.user.has_perm(
            "purchases.add_supplier"
        )
        context["can_change_supplier"] = self.request.user.has_perm(
            "purchases.change_supplier"
        )
        return context


@permission_required("purchases.add_supplier", raise_exception=True)
@require_http_methods(["GET", "POST"])
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                supplier = form.save()
        except IntegrityError:
            form.add_error("name", "Já existe um fornecedor com este nome.")
        else:
            messages.success(request, f"O fornecedor “{supplier.name}” foi criado.")
            return redirect("purchases:supplier_list")

    return render(
        request,
        "purchases/supplier_form.html",
        {
            "form": form,
            "form_title": "Novo fornecedor",
            "submit_label": "Criar fornecedor",
        },
    )


@permission_required("purchases.change_supplier", raise_exception=True)
@require_http_methods(["GET", "POST"])
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                supplier = form.save()
        except IntegrityError:
            form.add_error("name", "Já existe um fornecedor com este nome.")
        else:
            messages.success(request, f"O fornecedor “{supplier.name}” foi atualizado.")
            return redirect("purchases:supplier_list")

    return render(
        request,
        "purchases/supplier_form.html",
        {
            "form": form,
            "supplier": supplier,
            "form_title": "Editar fornecedor",
            "submit_label": "Guardar alterações",
        },
    )


class PurchaseListView(PermissionRequiredMixin, ListView):
    permission_required = "purchases.view_purchase"
    model = Purchase
    paginate_by = 20
    context_object_name = "purchases"
    template_name = "purchases/purchase_list.html"

    def get_filter_form(self):
        if not hasattr(self, "_filter_form"):
            form = PurchaseFilterForm(self.request.GET or None)
            if not self.request.user.has_perm("projects.view_project"):
                form.fields.pop("project")
            self._filter_form = form
        return self._filter_form

    def get_queryset(self):
        queryset = super().get_queryset().select_related("supplier")
        queryset = queryset.annotate(item_count=Count("items", distinct=True))
        form = self.get_filter_form()

        if form.is_valid():
            query = form.cleaned_data["q"].strip()
            supplier = form.cleaned_data.get("supplier")
            project = form.cleaned_data.get("project")
        else:
            query = ""
            supplier = None
            project = None

        if query:
            queryset = queryset.filter(
                Q(supplier__name__icontains=query)
                | Q(items__description__icontains=query)
                | Q(items__item__name__icontains=query)
                | Q(notes__icontains=query)
            ).distinct()
        if supplier is not None:
            queryset = queryset.filter(supplier=supplier)
        if project is not None:
            project_purchases = Purchase.objects.filter(
                items__movements__movement_type="initial_entry",
                items__movements__cancelled_at__isnull=True,
                items__movements__to_location__project=project,
            ).values("pk")
            queryset = queryset.filter(pk__in=project_purchases)

        return queryset.order_by("-purchase_date", "-created_at")

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return ["purchases/partials/purchase_results.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        context["can_add_purchase"] = self.request.user.has_perm(
            "purchases.add_purchase"
        )
        context["can_view_suppliers"] = self.request.user.has_perm(
            "purchases.view_supplier"
        )
        context["can_view_projects"] = self.request.user.has_perm(
            "projects.view_project"
        )
        return context


def _purchase_lines(purchase):
    movements = StockMovement.objects.select_related(
        "to_location",
        "to_location__project",
        "from_location",
        "created_by",
        "cancelled_by",
    ).order_by("-movement_date", "-created_at")
    lines = list(
        purchase.items.select_related("item")
        .annotate(
            active_received=Sum(
                "movements__quantity",
                filter=Q(
                    movements__movement_type=StockMovement.Type.INITIAL_ENTRY,
                    movements__cancelled_at__isnull=True,
                ),
            )
        )
        .prefetch_related(Prefetch("movements", queryset=movements))
        .order_by("pk")
    )
    for line in lines:
        if line.active_received is None:
            line.active_received = Decimal("0.000")
    return lines


def _purchase_detail_context(request, purchase, *, receipt_form=None, receipt_line=None):
    lines = _purchase_lines(purchase)
    can_change = request.user.has_perm("purchases.change_purchase")
    can_receive = can_change and request.user.has_perm("inventory.view_location")
    warehouse = (
        Location.objects.filter(location_type=Location.Type.WAREHOUSE)
        .order_by("pk")
        .first()
    )

    for line in lines:
        line.receipt_form = None
        if not can_receive or line.remaining_quantity <= 0:
            continue
        if receipt_form is not None and line.pk == receipt_line.pk:
            line.receipt_form = receipt_form
        elif line.item.is_active:
            line.receipt_form = ReceiptForm(
                item=line,
                initial={
                    "location": warehouse.pk if warehouse else None,
                    "quantity": line.remaining_quantity,
                },
            )

    return {
        "purchase": purchase,
        "items": lines,
        "can_change_purchase": can_change,
        "can_receive": can_receive,
    }


class PurchaseDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "purchases.view_purchase"
    model = Purchase
    context_object_name = "purchase"
    template_name = "purchases/purchase_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("supplier")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_purchase_detail_context(self.request, self.object))
        return context


@permission_required("purchases.add_purchase", raise_exception=True)
@require_http_methods(["GET", "POST"])
def purchase_create(request):
    purchase = Purchase()
    wizard_initial_step = 1
    if request.method == "POST":
        form = PurchaseForm(request.POST)
        formset = PurchaseItemFormSet(
            request.POST, instance=purchase, prefix="items"
        )
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                purchase = form.save(commit=False)
                purchase.total = Decimal("0.00")
                purchase.save()
                formset.instance = purchase
                formset.save()
                recalculate_purchase_total(purchase)
            messages.success(request, "A compra foi registada.")
            return redirect(purchase.get_absolute_url())
        wizard_initial_step = _purchase_wizard_step(form, formset)
    else:
        form = PurchaseForm()
        formset = PurchaseItemFormSet(instance=purchase, prefix="items")

    return render(
        request,
        "purchases/purchase_form.html",
        {
            "form": form,
            "formset": formset,
            "form_title": "Nova compra",
            "submit_label": "Registar compra",
            "wizard_initial_step": wizard_initial_step,
        },
    )


@permission_required("purchases.change_purchase", raise_exception=True)
@require_http_methods(["GET", "POST"])
def purchase_update(request, pk):
    with transaction.atomic():
        purchase = get_object_or_404(Purchase.objects.select_for_update(), pk=pk)
        items = PurchaseItem.objects.select_for_update().filter(purchase=purchase)
        wizard_initial_step = 1

        if request.method == "POST":
            form = PurchaseForm(request.POST, instance=purchase)
            formset = PurchaseItemFormSet(
                request.POST,
                instance=purchase,
                queryset=items,
                prefix="items",
            )
            if form.is_valid() and formset.is_valid():
                purchase = form.save()
                formset.save()
                recalculate_purchase_total(purchase)
                messages.success(request, "A compra foi atualizada.")
                return redirect(purchase.get_absolute_url())
            wizard_initial_step = _purchase_wizard_step(form, formset)
        else:
            form = PurchaseForm(instance=purchase)
            formset = PurchaseItemFormSet(
                instance=purchase,
                queryset=items,
                prefix="items",
            )

        return render(
            request,
            "purchases/purchase_form.html",
            {
                "form": form,
                "formset": formset,
                "purchase": purchase,
                "form_title": "Editar compra",
                "submit_label": "Guardar alterações",
                "wizard_initial_step": wizard_initial_step,
            },
        )


@permission_required(
    ("purchases.change_purchase", "inventory.view_location"),
    raise_exception=True,
)
@require_POST
def purchase_receive(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.select_related("supplier"),
        pk=pk,
    )
    try:
        item_pk = int(request.POST.get("item_pk", ""))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Linha inválida.")

    line = get_object_or_404(
        PurchaseItem.objects.select_related("purchase", "item"),
        pk=item_pk,
        purchase=purchase,
    )
    form = ReceiptForm(request.POST, item=line)

    if form.is_valid():
        try:
            receive_purchase_item(
                purchase_item=line,
                location=form.cleaned_data["location"],
                quantity=form.cleaned_data["quantity"],
                movement_date=form.cleaned_data["movement_date"],
                user=request.user,
            )
        except ValidationError as error:
            form.add_error(None, error.messages)
        else:
            messages.success(request, "A receção foi registada.")
            return redirect(purchase.get_absolute_url())

    return render(
        request,
        "purchases/purchase_detail.html",
        _purchase_detail_context(
            request,
            purchase,
            receipt_form=form,
            receipt_line=line,
        ),
    )


@require_GET
def purchase_item_row(request):
    user = request.user
    if not (
        user.has_perm("purchases.add_purchase")
        or user.has_perm("purchases.change_purchase")
    ):
        raise PermissionDenied

    raw_total = request.GET.get("items-TOTAL_FORMS", "1")
    try:
        total = max(1, int(raw_total))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Número de linhas inválido.")

    if total >= 50:
        return HttpResponseBadRequest("Máximo de 50 linhas por compra.")

    formset = PurchaseItemFormSet(instance=Purchase(), prefix="items")
    form = formset.empty_form
    form.prefix = f"items-{total}"
    form.auto_id = "id_%s"

    return render(
        request,
        "purchases/partials/purchase_item_row.html",
        {
            "form": form,
            "total_forms": total + 1,
        },
    )
