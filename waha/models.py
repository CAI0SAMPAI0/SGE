from django.conf import settings
from django.db import models


class WahaSession(models.Model):
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='waha_session')
    session_name = models.CharField(max_length=100, unique=True)
    is_connected = models.BooleanField(default=False)
    qr_code = models.TextField(blank=True)
    webhook_token = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tenant.name} - {"Conectado" if self.is_connected else "Desconectado"}'
