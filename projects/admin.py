from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "start_date", "archived_at", "updated_at")
    list_filter = ("status", "archived_at")
    search_fields = ("name", "address")
    date_hierarchy = "start_date"
    ordering = ("name",)
    readonly_fields = ("archived_at", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_archived:
            return False
        return super().has_change_permission(request, obj)
