from django import forms
from django.forms.models import BaseInlineFormSet, inlineformset_factory

from .forms import PurchaseItemForm
from .models import Purchase, PurchaseItem


class BasePurchaseItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        has_items = False
        for form in self.forms:
            cleaned_data = getattr(form, "cleaned_data", None)
            if not cleaned_data:
                continue
            if cleaned_data.get("DELETE"):
                instance = form.instance
                if instance.pk and instance.movements.exists():
                    form.add_error(
                        "DELETE",
                        "Não é possível eliminar uma linha com movimentos registados.",
                    )
                continue

            if cleaned_data.get("item"):
                has_items = True

            quantity = cleaned_data.get("quantity")
            instance = form.instance
            if quantity is not None and instance.pk:
                received = instance.get_active_received_quantity()
                if quantity < received:
                    form.add_error(
                        "quantity",
                        (
                            "A quantidade não pode ser inferior à quantidade "
                            f"já recebida ({received})."
                        ),
                    )

        if not has_items:
            raise forms.ValidationError("A compra tem de ter pelo menos uma linha.")


PurchaseItemFormSet = inlineformset_factory(
    Purchase,
    PurchaseItem,
    form=PurchaseItemForm,
    formset=BasePurchaseItemFormSet,
    extra=1,
    can_delete=True,
    max_num=50,
    validate_max=True,
)
