from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="projects:list", permanent=False)),
    path("admin/", admin.site.urls),
    path(
        "login/",
        LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("search/", views.search, name="search"),
    path(
        "ajuda/",
        TemplateView.as_view(template_name="help.html"),
        name="help",
    ),
    path("projects/", include("projects.urls")),
    path("purchases/", include("purchases.urls")),
    path("inventory/", include("inventory.urls")),
]
