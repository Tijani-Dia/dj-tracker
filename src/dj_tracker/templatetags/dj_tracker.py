from datetime import timedelta

from django import template

register = template.Library()


@register.filter
def duration_in_ms(value):
    return round(value / timedelta(milliseconds=1), 2)
