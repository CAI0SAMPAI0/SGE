from django import template

register = template.Library()

FIELD_LABELS = {
    'title': 'Nome do Produto',
    'category_name': 'Categoria',
    'brand_name': 'Marca',
    'cost_price': 'Preco de Custo',
    'selling_price': 'Preco de Venda',
    'quantity': 'Quantidade',
    'serie_number': 'Numero de Serie',
}


@register.filter
def get_item(d, key):
    return d.get(key, '') if isinstance(d, dict) else ''


@register.filter
def split(value, sep=','):
    if not value:
        return []
    return [v.strip() for v in value.split(sep)]


@register.filter
def field_label(value):
    return FIELD_LABELS.get(value, value)
