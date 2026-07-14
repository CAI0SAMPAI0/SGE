from django.utils.deprecation import MiddlewareMixin


class TenantMiddleware(MiddlewareMixin):
    """Seta request.tenant a partir do profile do usuario autenticado."""

    def process_request(self, request):
        request.tenant = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile:
                request.tenant = profile.tenant
