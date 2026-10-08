from django import template

register = template.Library()

@register.filter(name='endswith')
def endswith(value, suffix):
    return str(value).endswith(suffix)

@register.filter(name='startswith')
def startswith(value, prefix):
    return str(value).startswith(prefix)