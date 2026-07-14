from django.db import models
from tenants.models import Tenant


class Brand(models.Model):
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='brands',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['name']

        
    def __str__(self):
        return self.name
    