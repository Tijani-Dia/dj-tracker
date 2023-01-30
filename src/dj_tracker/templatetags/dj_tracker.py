from django import template

register = template.Library()


@register.filter
def total_queries(qs_trackings):
    return sum(qs_tracking.num_occurrences for qs_tracking in qs_trackings)
