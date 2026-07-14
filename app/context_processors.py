from django.conf import settings
from .models import UserProfile


def user_theme(request):
    """Injecta o tema do usuario no contexto de template."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'user_theme': 'dark'}
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return {'user_theme': profile.theme}
