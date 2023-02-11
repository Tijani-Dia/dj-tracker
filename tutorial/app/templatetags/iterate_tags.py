from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.tag("iterate")
def do_iterate(parser, token):
    bits = token.split_contents()
    sequence = parser.compile_filter(bits[-1])
    nodeiterate_loop = parser.parse(("enditerate",))
    parser.delete_first_token()
    return IterateNode(bits[1], sequence, nodeiterate_loop)


class IterateNode(template.Node):
    def __init__(self, loopvar, sequence, nodelist_loop):
        self.loopvar = loopvar
        self.sequence = sequence
        self.nodelist_loop = nodelist_loop

    def render(self, context):
        nodelist = []
        loopvar = self.loopvar
        nodelist_loop = self.nodelist_loop

        with context.push():
            for item in self.sequence.resolve(context, ignore_failures=True):
                context[loopvar] = item
                nodelist.extend(
                    node.render_annotated(context) for node in nodelist_loop
                )

        return mark_safe("".join(nodelist))
