from django.db import models


class Brand(models.Model):
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

        
    def __str__(self):
        return self.name
    