from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="projects:list", permanent=False)),
    path("admin/", admin.site.urls),
    path("search/", views.search, name="search"),
    path("projects/", include("projects.urls")),
    path("purchases/", include("purchases.urls")),
    path("inventory/", include("inventory.urls")),
]
