from django import template

register = template.Library()

@register.filter(name='endswith')
def endswith(value, suffix):
    if value is None or suffix is None:
        return False
    return str(value).strip().lower().endswith(str(suffix).strip().lower())

@register.filter(name='startswith')
def startswith(value, prefix):
    if value is None or prefix is None:
        return False
    return str(value).strip().lower().startswith(str(prefix).strip().lower())
