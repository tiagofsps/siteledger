from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Item, Location, StockMovement

POSITIVE_QUANTITY = Decimal("0.001")


def active_items():
    return Item.objects.filter(is_active=True)


def active_locations():
    return Location.objects.filter(is_active=True)


def incoming_locations():
    return active_locations().filter(
        Q(location_type=Location.Type.WAREHOUSE)
        | Q(project__archived_at__isnull=True)
    )


def outgoing_locations():
    return active_locations()


def project_locations():
    return active_locations().filter(location_type=Location.Type.PROJECT)


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["name", "category", "unit", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class MovementFormMixin:
    def _configure_choices(self, *, items=None, locations=None):
        self.fields["item"].queryset = items or active_items()
        if "to_location" in self.fields:
            self.fields["to_location"].queryset = locations or incoming_locations()
        if "from_location" in self.fields:
            self.fields["from_location"].queryset = locations or outgoing_locations()


class InitialEntryForm(MovementFormMixin, forms.Form):
    item = forms.ModelChoiceField(
        label="Artigo",
        queryset=Item.objects.none(),
    )
    to_location = forms.ModelChoiceField(
        label="Localização de destino",
        queryset=Location.objects.none(),
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        max_digits=12,
        decimal_places=3,
        min_value=POSITIVE_QUANTITY,
    )
    movement_date = forms.DateField(
        label="Data do movimento",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    notes = forms.CharField(
        label="Observações",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_choices()


class TransferForm(MovementFormMixin, forms.Form):
    item = forms.ModelChoiceField(
        label="Artigo",
        queryset=Item.objects.none(),
    )
    from_location = forms.ModelChoiceField(
        label="Localização de origem",
        queryset=Location.objects.none(),
    )
    to_location = forms.ModelChoiceField(
        label="Localização de destino",
        queryset=Location.objects.none(),
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        max_digits=12,
        decimal_places=3,
        min_value=POSITIVE_QUANTITY,
    )
    movement_date = forms.DateField(
        label="Data do movimento",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    notes = forms.CharField(
        label="Observações",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = active_items()
        self.fields["from_location"].queryset = outgoing_locations()
        self.fields["to_location"].queryset = incoming_locations()

    def clean(self):
        cleaned_data = super().clean()
        from_location = cleaned_data.get("from_location")
        to_location = cleaned_data.get("to_location")
        if from_location and to_location and from_location.pk == to_location.pk:
            raise forms.ValidationError(
                "A origem e o destino têm de ser diferentes."
            )
        return cleaned_data


class ReturnToWarehouseForm(MovementFormMixin, forms.Form):
    item = forms.ModelChoiceField(
        label="Artigo",
        queryset=Item.objects.none(),
    )
    from_location = forms.ModelChoiceField(
        label="Localização de origem",
        queryset=Location.objects.none(),
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        max_digits=12,
        decimal_places=3,
        min_value=POSITIVE_QUANTITY,
    )
    movement_date = forms.DateField(
        label="Data do movimento",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    notes = forms.CharField(
        label="Observações",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = active_items()
        self.fields["from_location"].queryset = project_locations()


class AdjustmentInForm(MovementFormMixin, forms.Form):
    item = forms.ModelChoiceField(
        label="Artigo",
        queryset=Item.objects.none(),
    )
    to_location = forms.ModelChoiceField(
        label="Localização",
        queryset=Location.objects.none(),
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        max_digits=12,
        decimal_places=3,
        min_value=POSITIVE_QUANTITY,
    )
    movement_date = forms.DateField(
        label="Data do movimento",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    notes = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_choices()


class AdjustmentOutForm(MovementFormMixin, forms.Form):
    item = forms.ModelChoiceField(
        label="Artigo",
        queryset=Item.objects.none(),
    )
    from_location = forms.ModelChoiceField(
        label="Localização",
        queryset=Location.objects.none(),
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        max_digits=12,
        decimal_places=3,
        min_value=POSITIVE_QUANTITY,
    )
    movement_date = forms.DateField(
        label="Data do movimento",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    notes = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_choices()


class MovementFilterForm(forms.Form):
    item = forms.ModelChoiceField(
        label="Artigo",
        queryset=Item.objects.all(),
        required=False,
        empty_label="Todos os artigos",
    )
    location = forms.ModelChoiceField(
        label="Localização",
        queryset=Location.objects.all(),
        required=False,
        empty_label="Todas as localizações",
    )
    movement_type = forms.ChoiceField(
        label="Tipo",
        choices=[("", "Todos os tipos"), *StockMovement.Type.choices],
        required=False,
    )


class CancellationForm(forms.Form):
    reason = forms.CharField(
        label="Motivo do cancelamento",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
