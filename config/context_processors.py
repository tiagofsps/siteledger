"""Template context shared by every page."""

from django.conf import settings


def branding(request):
    """Expose the deployment branding to templates as `branding`."""
    return {"branding": settings.BRANDING}
