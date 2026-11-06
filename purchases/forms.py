from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import Q
from django.utils import timezone

from inventory.models import Item, Location
from inventory.units import is_discrete, quantity_step, validate_quantity
from inventory.widgets import UnitSelect
from projects.models import Project

from .models import Purchase, PurchaseItem, Supplier
from .services import active_received_quantity


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ("name", "is_active")

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        duplicates = Supplier.objects.filter(name__iexact=name)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError(
                "Já existe um fornecedor com este nome.",
                code="duplicate_supplier",
            )
        return name


class SupplierFilterForm(forms.Form):
    q = forms.CharField(
        label="Pesquisar",
        required=False,
        max_length=200,
        widget=forms.SearchInput,
    )


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ("supplier", "purchase_date", "notes")
        widgets = {
            "purchase_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        suppliers = Supplier.objects.filter(is_active=True)
        if self.instance.pk:
            suppliers = Supplier.objects.filter(
                Q(pk=self.instance.supplier_id) | Q(is_active=True)
            )
        self.fields["supplier"].queryset = suppliers.order_by("name")
        if not self.instance.pk and not self.initial.get("purchase_date"):
            self.initial["purchase_date"] = date.today()


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ("item", "quantity", "unit_price")
        labels = {
            "item": "Artigo do catálogo",
            "quantity": "Quantidade",
            "unit_price": "Preço unitário",
        }
        widgets = {
            "item": UnitSelect,
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        items = Item.objects.filter(is_active=True)
        if self.instance.pk and self.instance.item_id:
            items = Item.objects.filter(
                Q(pk=self.instance.item_id) | Q(is_active=True)
            )
        self.fields["item"].queryset = items.order_by("name")
        self.fields["item"].empty_label = "Selecione um artigo"
        self.fields["quantity"].min_value = Decimal("0.001")
        self.fields["quantity"].validators.append(MinValueValidator(Decimal("0.001")))
        self.fields["unit_price"].required = True
        self.fields["unit_price"].min_value = Decimal("0.00")
        self.fields["unit_price"].validators.append(MinValueValidator(Decimal("0.00")))

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get("item")
        quantity = cleaned_data.get("quantity")

        if item is not None and quantity is not None:
            try:
                validate_quantity(item.unit, quantity)
            except ValidationError as error:
                self.add_error("quantity", error)

        if (
            self.instance.pk
            and self.instance.movements.exists()
            and "item" in self.changed_data
        ):
            self.add_error(
                "item",
                "Não é possível alterar o artigo depois de existirem receções.",
            )

        return cleaned_data

    def save(self, commit=True):
        previous_item_id = self.initial.get("item")
        instance = super().save(commit=False)
        item = self.cleaned_data["item"]
        instance.item = item
        if previous_item_id != item.pk:
            instance.description = item.name
            instance.unit = item.unit
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class PurchaseFilterForm(forms.Form):
    q = forms.CharField(
        label="Pesquisar",
        required=False,
        max_length=200,
        widget=forms.SearchInput,
    )
    supplier = forms.ModelChoiceField(
        label="Fornecedor",
        queryset=Supplier.objects.none(),
        required=False,
        empty_label="Todos",
    )
    project = forms.ModelChoiceField(
        label="Obra",
        queryset=Project.objects.none(),
        required=False,
        empty_label="Todas",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.order_by("name")
        self.fields["project"].queryset = Project.objects.order_by("name")


class ReceiptForm(forms.Form):
    location = forms.ModelChoiceField(
        label="Localização",
        queryset=Location.objects.none(),
        empty_label="Selecione uma localização",
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
        widget=forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
    )
    movement_date = forms.DateField(
        label="Data da receção",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.item = item
        self.fields["location"].queryset = (
            Location.objects.filter(is_active=True)
            .select_related("project")
            .order_by("name")
        )
        self.fields["quantity"].validators.append(MinValueValidator(Decimal("0.001")))
        if item is not None:
            self.fields["quantity"].widget.attrs["step"] = quantity_step(item.unit)
            if is_discrete(item.unit):
                self.fields["quantity"].widget.attrs["min"] = "1"

    def clean(self):
        cleaned_data = super().clean()
        location = cleaned_data.get("location")
        quantity = cleaned_data.get("quantity")
        if location is None or quantity is None or self.item is None:
            return cleaned_data

        if not location.is_active:
            self.add_error("location", "A localização está inativa.")
        if location.location_type == Location.Type.PROJECT and location.project.is_archived:
            self.add_error(
                "location",
                "Não é possível receber quantidades numa obra arquivada.",
            )

        try:
            validate_quantity(self.item.unit, quantity)
        except ValidationError as error:
            self.add_error("quantity", error)

        received = active_received_quantity(self.item)
        if received + quantity > self.item.quantity:
            self.add_error(
                "quantity",
                (
                    "A quantidade excede o que falta receber nesta linha "
                    f"({self.item.quantity - received})."
                ),
            )
        return cleaned_data
