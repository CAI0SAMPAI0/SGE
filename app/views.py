import json
import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ai.models import AIResult
from . import metrics
from .models import SiteSettings

logger = logging.getLogger(__name__)


@login_required(login_url='login')
def home(request):
    product_metrics = metrics.get_product_metrics()
    sales_metrics = metrics.get_sales_metrics()
    graphic_product_category_metric = metrics.get_graphic_product_category_metric()
    graphic_product_brand_metric = metrics.get_graphic_product_brand_metric()
    daily_sales_data = metrics.get_daily_sales_data()
    daily_sales_quantity_data = metrics.get_daily_sales_quantity_data()
    ai_result = AIResult.objects.first()
    ai_result = ai_result.result if ai_result else ''

    context = {
        'product_metrics': product_metrics,
        'sales_metrics': sales_metrics,
        'product_count_by_category': json.dumps(graphic_product_category_metric),
        'product_count_by_brand': json.dumps(graphic_product_brand_metric),
        'daily_sales_data': json.dumps(daily_sales_data),
        'daily_sales_quantity_data': json.dumps(daily_sales_quantity_data),
        'ai_result': ai_result,
    }

    return render(request, 'home.html', context)

def ia_history(request):
    results = AIResult.objects.all().order_by('-created_at')
    return render(request, 'ia/history.html', {'results': results})


def settings_view(request):
    """Render and persist site settings.
    GET → exibe formulário já preenchido com os valores atuais.
    POST → salva as alterações e recarrega a página.
    """
    # garante existência de um registro singleton
    settings_obj, _ = SiteSettings.objects.get_or_create(pk=1)

    if request.method == "POST":
        theme = request.POST.get("theme", settings_obj.theme)
        limit = request.POST.get("results_limit", settings_obj.results_limit)
        # validação simples
        try:
            limit = int(limit)
            if limit < 1:
                raise ValueError
        except (ValueError, TypeError):
            limit = settings_obj.results_limit
        settings_obj.theme = theme
        settings_obj.results_limit = limit
        settings_obj.save()
        logger.info("Site settings updated: %s", settings_obj)
        # renderiza novamente para mostrar valores atualizados
        return render(request, "settings/settings.html", {"settings": settings_obj})

    # GET – somente exibe
    return render(request, "settings/settings.html", {"settings": settings_obj})

