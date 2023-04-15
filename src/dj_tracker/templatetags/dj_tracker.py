from django import template

register = template.Library()


@register.filter
def total_queries(queries):
    return sum(query.num_occurrences for query in queries)


@register.tag
def preserve_query_parameters(parser, token):
    params = {}

    for pair in token.split_contents()[1:]:
        s = pair.split("=", 1)
        params[s[0]] = parser.compile_filter(s[1])

    return PreserveQueryParameters(params)


class PreserveQueryParameters(template.Node):
    # https://djangosnippets.org/snippets/2428/
    def __init__(self, params):
        self.params = params

    def render(self, context):
        params = context["request"].GET.copy()
        params.update(
            (key, value.resolve(context)) for key, value in self.params.items()
        )
        return "?%s" % params.urlencode()
