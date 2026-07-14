from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    return d.get(key, '') if isinstance(d, dict) else ''


@register.filter
def split(value, sep=','):
    return value.split(sep) if value else []
