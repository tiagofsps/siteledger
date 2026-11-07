from django.test import TestCase

from inventory.forms import (
    AdjustmentOutForm,
    InitialEntryForm,
    ReturnToWarehouseForm,
    TransferForm,
    project_locations,
)
from inventory.models import Location
from inventory.widgets import UnitSelect

from .base import create_item, project_location, warehouse


class ProjectLocationsTests(TestCase):
    def test_project_locations_returns_only_active_projects(self):
        warehouse()
        project_location()

        locations = project_locations()

        self.assertTrue(locations.exists())
        self.assertEqual(
            set(locations.values_list("location_type", flat=True)),
            {Location.Type.PROJECT},
        )


class ReturnToWarehouseFormTests(TestCase):
    def test_form_wires_active_items_and_project_locations(self):
        item = create_item()
        location = project_location()
        warehouse()

        form = ReturnToWarehouseForm()

        self.assertIn(item, form.fields["item"].queryset)
        self.assertEqual(
            set(form.fields["from_location"].queryset.values_list("pk", flat=True)),
            {location.pk},
        )


class AdjustmentOutFormTests(TestCase):
    def test_form_wires_active_items_and_outgoing_locations(self):
        item = create_item()
        location = warehouse()

        form = AdjustmentOutForm()

        self.assertIn(item, form.fields["item"].queryset)
        self.assertIn(
            location,
            form.fields["from_location"].queryset,
        )


class TransferFormTests(TestCase):
    def test_rejects_identical_source_and_destination(self):
        item = create_item()
        location = warehouse()

        form = TransferForm(
            data={
                "item": item.pk,
                "from_location": location.pk,
                "to_location": location.pk,
                "quantity": "1.000",
                "movement_date": "2026-01-20",
                "notes": "",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_clean_without_item_or_quantity_returns_early(self):
        form = InitialEntryForm(data={})

        self.assertFalse(form.is_valid())
        self.assertIn("item", form.errors)


class UnitSelectTests(TestCase):
    def test_merges_custom_attrs_with_default_class(self):
        widget = UnitSelect(attrs={"data-foo": "bar"})

        self.assertEqual(widget.attrs["class"], "item-select")
        self.assertEqual(widget.attrs["data-foo"], "bar")
