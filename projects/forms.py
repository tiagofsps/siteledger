from django import forms

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "address", "description", "start_date", "status")
        widgets = {
            "address": forms.TextInput(attrs={"maxlength": 300}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }


class ProjectFilterForm(forms.Form):
    q = forms.CharField(
        label="Pesquisar",
        required=False,
        max_length=200,
        widget=forms.SearchInput,
    )
    estado = forms.ChoiceField(
        label="Estado",
        required=False,
        choices=(
            ("", "Ativas"),
            (Project.Status.PLANNED, "Planeadas"),
            (Project.Status.IN_PROGRESS, "Em curso"),
            (Project.Status.COMPLETED, "Concluídas"),
            ("archived", "Arquivadas"),
            ("all", "Todas"),
        ),
    )
