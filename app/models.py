from django.db import models


class SiteSettings(models.Model):
    """Armazena opções globais de UI da aplicação."""

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
        help_text="Limite padrão de resultados exibidos pela IA.",
    )

    class Meta:
        verbose_name = "Configuração do Site"
        verbose_name_plural = "Configurações do Site"

    def __str__(self) -> str:
        return f"Settings (theme={self.theme}, limit={self.results_limit})"
