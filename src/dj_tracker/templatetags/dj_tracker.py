from django import VERSION as DJANGO_VERSION
from django import template

register = template.Library()


@register.filter
def total_queries(queries):
    return sum(query.num_occurrences for query in queries)


@register.tag
def preserve_query_parameters(parser, token):
    # https://djangosnippets.org/snippets/2428/
    params = {}

    for pair in token.split_contents()[1:]:
        s = pair.split("=", 1)
        params[s[0]] = parser.compile_filter(s[1])

    return PreserveQueryParameters(params)


class PreserveQueryParameters(template.Node):
    def __init__(self, params):
        self.params = params

    def render(self, context):
        params = context["request"].GET.copy()
        params.update(
            (key, value.resolve(context)) for key, value in self.params.items()
        )
        return "?%s" % params.urlencode()


if DJANGO_VERSION[0] < 4 or (DJANGO_VERSION[0] == 4 and DJANGO_VERSION[1] < 1):
    from django.utils.safestring import mark_safe

    @register.filter
    def form_as_div(form):
        return mark_safe(form.as_p().replace("<p>", "<div>").replace("</p>", "</div>"))

else:

    @register.filter
    def form_as_div(form):
        return form.as_div()
