from rest_framework import generics
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView
from app.mixins import TenantFilterMixin
from app import metrics
from . import models, forms, serializers


class OutflowListView(LoginRequiredMixin, PermissionRequiredMixin, TenantFilterMixin, ListView):
    model = models.Outflow
    template_name = 'outflow_list.html'
    context_object_name = 'outflows'
    paginate_by = 10
    permission_required = 'outflows.view_outflow'

    def get_queryset(self):
        queryset = super().get_queryset()
        product = self.request.GET.get('product')

        if product:
            queryset = queryset.filter(product__title__icontains=product)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product_metrics'] = metrics.get_product_metrics(tenant=self.request.tenant)
        context['sales_metrics'] = metrics.get_sales_metrics(tenant=self.request.tenant)
        return context


class OutflowCreateView(LoginRequiredMixin, PermissionRequiredMixin, TenantFilterMixin, CreateView):
    model = models.Outflow
    template_name = 'outflow_create.html'
    form_class = forms.OutflowForm
    success_url = reverse_lazy('outflow_list')
    permission_required = 'outflows.add_outflow'


class OutflowDetailView(LoginRequiredMixin, PermissionRequiredMixin, TenantFilterMixin, DetailView):
    model = models.Outflow
    template_name = 'outflow_detail.html'
    permission_required = 'outflows.view_outflow'


class OutflowCreateListAPIView(generics.ListCreateAPIView):
    queryset = models.Outflow.objects.all()
    serializer_class = serializers.OutflowSerializer


class OutflowRetrieveAPIView(generics.RetrieveAPIView):
    queryset = models.Outflow.objects.all()
    serializer_class = serializers.OutflowSerializer
