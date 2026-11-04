from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import (
    AdjustmentInForm,
    AdjustmentOutForm,
    CancellationForm,
    InitialEntryForm,
    ItemForm,
    MovementFilterForm,
    ReturnToWarehouseForm,
    TransferForm,
)
from .models import Item, Location, StockMovement
from .services import (
    cancel_stock_movement,
    create_adjustment_in,
    create_adjustment_out,
    create_initial_entry,
    create_transfer,
    get_item_location_balances,
    return_to_warehouse,
)

MOVEMENT_PERMISSIONS = [
    "inventory.add_stockmovement",
    "inventory.view_item",
    "inventory.view_location",
]


class ItemListView(PermissionRequiredMixin, ListView):
    permission_required = "inventory.view_item"
    model = Item
    paginate_by = 20
    context_object_name = "items"
    template_name = "inventory/item_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(unit__icontains=query)
                | Q(description__icontains=query)
            )
        return queryset

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return ["inventory/partials/item_results.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
        context["can_add_item"] = self.request.user.has_perm("inventory.add_item")
        return context


class ItemDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_item"
    model = Item
    context_object_name = "item"
    template_name = "inventory/item_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_view_movements"] = self.request.user.has_perm(
            "inventory.view_stockmovement"
        )
        if context["can_view_movements"]:
            context["balances"] = get_item_location_balances(self.object)
            context["movements"] = (
                self.object.movements.select_related(
                    "from_location",
                    "to_location",
                    "created_by",
                    "cancelled_by",
                )[:50]
            )
        else:
            context["balances"] = []
            context["movements"] = StockMovement.objects.none()
        context["can_change_item"] = self.request.user.has_perm(
            "inventory.change_item"
        )
        context["can_add_movement"] = self.request.user.has_perms(
            MOVEMENT_PERMISSIONS
        )
        context["can_cancel_movement"] = self.request.user.has_perm(
            "inventory.change_stockmovement"
        )
        return context


class ItemCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "inventory.add_item"
    model = Item
    form_class = ItemForm
    template_name = "inventory/item_form.html"
    extra_context = {
        "form_title": "Novo artigo",
        "submit_label": "Criar artigo",
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"O artigo “{self.object.name}” foi criado.",
        )
        return response


class ItemUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "inventory.change_item"
    model = Item
    form_class = ItemForm
    template_name = "inventory/item_form.html"
    context_object_name = "item"
    extra_context = {
        "form_title": "Editar artigo",
        "submit_label": "Guardar alterações",
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"O artigo “{self.object.name}” foi atualizado.",
        )
        return response


class LocationListView(PermissionRequiredMixin, ListView):
    permission_required = "inventory.view_location"
    model = Location
    context_object_name = "locations"
    template_name = "inventory/location_list.html"

    def get_queryset(self):
        return super().get_queryset().select_related("project")


class MovementListView(PermissionRequiredMixin, ListView):
    permission_required = "inventory.view_stockmovement"
    model = StockMovement
    paginate_by = 30
    context_object_name = "movements"
    template_name = "inventory/movement_list.html"

    def get_filter_form(self):
        if not hasattr(self, "_filter_form"):
            self._filter_form = MovementFilterForm(self.request.GET or None)
        return self._filter_form

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "item",
            "from_location",
            "to_location",
            "created_by",
        )
        form = self.get_filter_form()
        if form.is_valid():
            query = form.cleaned_data["q"].strip()
            item = form.cleaned_data["item"]
            location = form.cleaned_data["location"]
            movement_type = form.cleaned_data["movement_type"]
            if query:
                queryset = queryset.filter(
                    Q(item__name__icontains=query)
                    | Q(notes__icontains=query)
                    | Q(from_location__name__icontains=query)
                    | Q(to_location__name__icontains=query)
                )
            if item:
                queryset = queryset.filter(item=item)
            if location:
                queryset = queryset.filter(
                    Q(from_location=location) | Q(to_location=location)
                )
            if movement_type:
                queryset = queryset.filter(movement_type=movement_type)
        return queryset

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return ["inventory/partials/movement_results.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        context["can_add_movement"] = self.request.user.has_perms(
            MOVEMENT_PERMISSIONS
        )
        context["can_cancel_movement"] = self.request.user.has_perm(
            "inventory.change_stockmovement"
        )
        return context


class MovementDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_stockmovement"
    model = StockMovement
    context_object_name = "movement"
    template_name = "inventory/movement_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "item",
            "from_location",
            "to_location",
            "purchase_item",
            "created_by",
            "cancelled_by",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_cancel_movement"] = self.request.user.has_perm(
            "inventory.change_stockmovement"
        )
        return context


def _create_movement_view(
    request,
    *,
    form_class,
    service,
    title,
    submit_label,
    success_message,
):
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            movement = service(user=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, success_message)
            return redirect(movement)

    wizard_initial_step = 1
    if request.method == "POST" and form.errors and set(form.errors) == {"notes"}:
        wizard_initial_step = 2

    return render(
        request,
        "inventory/movement_form.html",
        {
            "form": form,
            "form_title": title,
            "submit_label": submit_label,
            "wizard_initial_step": wizard_initial_step,
        },
    )


@require_GET
@permission_required(MOVEMENT_PERMISSIONS, raise_exception=True)
def movement_type_select(request):
    return render(request, "inventory/movement_type_select.html")


@require_http_methods(["GET", "POST"])
@permission_required(MOVEMENT_PERMISSIONS, raise_exception=True)
def initial_entry_create(request):
    return _create_movement_view(
        request,
        form_class=InitialEntryForm,
        service=create_initial_entry,
        title="Nova entrada inicial",
        submit_label="Registar entrada",
        success_message="Entrada inicial registada.",
    )


@require_http_methods(["GET", "POST"])
@permission_required(MOVEMENT_PERMISSIONS, raise_exception=True)
def transfer_create(request):
    return _create_movement_view(
        request,
        form_class=TransferForm,
        service=create_transfer,
        title="Nova transferência",
        submit_label="Registar transferência",
        success_message="Transferência registada.",
    )


@require_http_methods(["GET", "POST"])
@permission_required(MOVEMENT_PERMISSIONS, raise_exception=True)
def return_to_warehouse_create(request):
    return _create_movement_view(
        request,
        form_class=ReturnToWarehouseForm,
        service=return_to_warehouse,
        title="Devolver ao armazém",
        submit_label="Registar devolução",
        success_message="Devolução ao armazém registada.",
    )


@require_http_methods(["GET", "POST"])
@permission_required(MOVEMENT_PERMISSIONS, raise_exception=True)
def adjustment_in_create(request):
    return _create_movement_view(
        request,
        form_class=AdjustmentInForm,
        service=create_adjustment_in,
        title="Nova correção de entrada",
        submit_label="Registar correção",
        success_message="Correção de entrada registada.",
    )


@require_http_methods(["GET", "POST"])
@permission_required(MOVEMENT_PERMISSIONS, raise_exception=True)
def adjustment_out_create(request):
    return _create_movement_view(
        request,
        form_class=AdjustmentOutForm,
        service=create_adjustment_out,
        title="Nova correção de saída",
        submit_label="Registar correção",
        success_message="Correção de saída registada.",
    )


@require_http_methods(["GET", "POST"])
@permission_required("inventory.change_stockmovement", raise_exception=True)
def movement_cancel(request, pk):
    movement = get_object_or_404(
        StockMovement.objects.select_related(
            "item",
            "from_location",
            "to_location",
        ),
        pk=pk,
    )
    if movement.is_cancelled:
        messages.error(request, "O movimento já está cancelado.")
        return redirect(movement)

    form = CancellationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_stock_movement(
                movement=movement,
                user=request.user,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Movimento cancelado.")
            return redirect(movement)

    return render(
        request,
        "inventory/movement_cancel.html",
        {"movement": movement, "form": form},
    )
