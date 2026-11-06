from django import forms


class UnitSelect(forms.Select):
    """Item select that exposes each option's unit to the page script."""

    def __init__(self, attrs=None):
        merged = {"class": "item-select"}
        if attrs:
            merged.update(attrs)
        super().__init__(merged)

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex,
            attrs,
        )
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-unit"] = instance.unit
        return option
