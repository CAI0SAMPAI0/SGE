from django.conf import settings
from django.db import models


class SiteSettings(models.Model):
    """Armazena opcoes globais de UI da aplicacao."""

    THEME_CHOICES = [
        ("dark", "Escuro"),
        ("light", "Claro"),
    ]

    theme = models.CharField(
        max_length=5,
        choices=THEME_CHOICES,
        default="dark",
        help_text="Tema da interface (escuro ou claro).",
    )
    results_limit = models.PositiveIntegerField(
        default=20,
        help_text="Limite padrao de resultados exibidos pela IA.",
    )

    class Meta:
        verbose_name = "Configuracao do Site"
        verbose_name_plural = "Configuracoes do Site"

    def __str__(self) -> str:
        return f"Settings (theme={self.theme}, limit={self.results_limit})"


class UserProfile(models.Model):
    """Preferencias por usuario."""

    THEME_CHOICES = [
        ("dark", "Escuro"),
        ("light", "Claro"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
    )
    theme = models.CharField(
        max_length=5,
        choices=THEME_CHOICES,
        default="dark",
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    avatar_color = models.CharField(max_length=20, default="primary")

    def __str__(self):
        return f"{self.user.username} ({self.theme})"
