class TenantFilterMixin:
    """Filtra queryset por tenant e seta tenant em creates."""

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request, 'tenant') and self.request.tenant:
            qs = qs.filter(tenant=self.request.tenant)
        return qs

    def form_valid(self, form):
        if hasattr(self.request, 'tenant') and self.request.tenant:
            form.instance.tenant = self.request.tenant
        return super().form_valid(form)
