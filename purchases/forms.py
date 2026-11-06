from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import Q

from inventory.models import Item, Location
from projects.models import Project

from .models import Purchase, PurchaseItem, Supplier
from .services import active_allocated_quantity


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
        fields = ("item", "description", "unit", "quantity", "unit_price")
        labels = {
            "description": "Descrição",
            "unit": "Unidade",
            "unit_price": "Preço unitário",
        }
        widgets = {
            "unit": forms.TextInput(attrs={"list": "unit-options"}),
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
        self.fields["item"].empty_label = "Sem artigo do catálogo"
        self.fields["description"].required = False
        self.fields["unit"].required = False
        self.fields["unit_price"].required = True
        self.fields["quantity"].min_value = Decimal("0.001")
        self.fields["quantity"].validators.append(MinValueValidator(Decimal("0.001")))
        self.fields["unit_price"].min_value = Decimal("0.00")
        self.fields["unit_price"].validators.append(MinValueValidator(Decimal("0.00")))

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get("item")
        description = cleaned_data.get("description")
        unit = cleaned_data.get("unit")

        if item is not None:
            if not description:
                cleaned_data["description"] = item.name
            if not unit:
                cleaned_data["unit"] = item.unit
            elif unit.strip().casefold() != item.unit.strip().casefold():
                self.add_error(
                    "unit",
                    "A unidade tem de coincidir com a unidade de referência do artigo.",
                )
        else:
            if not description:
                self.add_error("description", "Este campo é obrigatório.")
            if not unit:
                self.add_error("unit", "Este campo é obrigatório.")
        return cleaned_data


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


class AllocationForm(forms.Form):
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

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.item = item
        self.fields["location"].queryset = (
            Location.objects.filter(is_active=True)
            .select_related("project")
            .order_by("name")
        )
        self.fields["quantity"].validators.append(MinValueValidator(Decimal("0.001")))

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
        if self.item.item_id is None:
            self.add_error(
                None,
                "O artigo da compra tem de estar associado ao catálogo antes de ser alocado.",
            )
            return cleaned_data

        allocated = active_allocated_quantity(self.item)
        if allocated + quantity > self.item.quantity:
            self.add_error(
                "quantity",
                (
                    "A quantidade excede o que falta receber nesta linha "
                    f"({self.item.quantity - allocated})."
                ),
            )
        return cleaned_data
