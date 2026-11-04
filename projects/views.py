from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import ProjectFilterForm, ProjectForm
from .models import Project


class ProjectListView(PermissionRequiredMixin, ListView):
    permission_required = "projects.view_project"
    model = Project
    paginate_by = 20
    context_object_name = "projects"
    template_name = "projects/project_list.html"

    def get_filter_form(self):
        if not hasattr(self, "_filter_form"):
            self._filter_form = ProjectFilterForm(self.request.GET or None)
        return self._filter_form

    def get_queryset(self):
        queryset = super().get_queryset()
        form = self.get_filter_form()

        if form.is_valid():
            query = form.cleaned_data["q"].strip()
            status = form.cleaned_data["estado"]
        else:
            query = ""
            status = ""

        if status == "archived":
            queryset = queryset.filter(archived_at__isnull=False)
        elif status == "all":
            pass
        elif status in Project.Status.values:
            queryset = queryset.filter(archived_at__isnull=True, status=status)
        else:
            queryset = queryset.filter(archived_at__isnull=True)

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(address__icontains=query)
            )

        return queryset

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return ["projects/partials/project_results.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        context["can_add_project"] = self.request.user.has_perm(
            "projects.add_project"
        )
        return context


class ProjectDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "projects.view_project"
    model = Project
    context_object_name = "project"
    template_name = "projects/project_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_change_project"] = self.request.user.has_perm(
            "projects.change_project"
        )
        context["can_view_purchases"] = self.request.user.has_perm(
            "purchases.view_purchase"
        )
        context["can_view_movements"] = self.request.user.has_perm(
            "inventory.view_stockmovement"
        )
        return context


class ProjectCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "projects.add_project"
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    extra_context = {
        "form_title": "Nova obra",
        "submit_label": "Criar obra",
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"A obra “{self.object.name}” foi criada.",
        )
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class ProjectUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "projects.change_project"
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    context_object_name = "project"
    extra_context = {
        "form_title": "Editar obra",
        "submit_label": "Guardar alterações",
    }

    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"A obra “{self.object.name}” foi atualizada.",
        )
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


@require_http_methods(["GET", "POST"])
@permission_required("projects.change_project", raise_exception=True)
def archive_project(request, pk):
    project = get_object_or_404(Project, pk=pk, archived_at__isnull=True)

    if request.method == "POST":
        project.archive()
        messages.success(request, f"A obra “{project.name}” foi arquivada.")
        return redirect(project.get_absolute_url())

    return render(
        request,
        "projects/project_confirm_archive.html",
        {"project": project},
    )


@require_http_methods(["GET", "POST"])
@permission_required("projects.change_project", raise_exception=True)
def unarchive_project(request, pk):
    project = get_object_or_404(Project, pk=pk, archived_at__isnull=False)

    if request.method == "POST":
        project.unarchive()
        messages.success(request, f"A obra “{project.name}” foi reativada.")
        return redirect(project.get_absolute_url())

    return render(
        request,
        "projects/project_confirm_unarchive.html",
        {"project": project},
    )
