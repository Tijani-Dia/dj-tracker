# `values`/`values_list` usage

When `dj-tracker` detects that no model attributes, except the ones needed to build model instances, are used for all instances of a queryset; it'll hint at using the [`.values` or `.values_list`](https://docs.djangoproject.com/en/4.1/topics/db/optimization/#use-queryset-values-and-values-list) methods.

## View - Template

Let's update our view to use `.values`:

```python
def books_list(request):
    only = ("title", "category__name", "author__first_name", "author__last_name")
    context = {
        "books": Book.objects.select_related("author", "category")
        .only(*only)
        .values(*only)
    }
    return render(request, "books.html", context)
```

We'll also need to update our templates since our `Book` instances are now dict objects that look as follows:

```python
{
    "title": "Harry Potter",
    "category__name": "Science Fiction",
    "author__first_name": "Joanne",
    "author__last_name": "Rowling"
}
```

```html
{% for book in books %}
    {{ book.title }} -({{ book.author__first_name }} {{book.author__last_name }}) - {{ book.category__name }}
{% endfor %}
```

## Profile

Let's run our profilers to see how our view performs now that we're using plain dicts instead of building custom model instances:

```console
Time in ms (25 calls) - Min: 40.05, Max: 72.93, Avg: 47.13

Memory - size in KiB (25 calls) - Min: 1008.73, Max: 1154.21, Avg: 1030.85
Memory - peak in KiB (25 calls) - Min: 2156.58, Max: 2302.35, Avg: 2178.71
```

Our new version is in average 2.5x faster (previous average was 115.76ms) and uses 2.7x less memory as well.

## Summary

`dj-tracker` keeps track of model attributes accessed to provide hints on when to use the [`.values`](https://docs.djangoproject.com/en/4.0/ref/models/querysets/#values) or [`.values_list`](https://docs.djangoproject.com/en/4.0/ref/models/querysets/#values-list) optimisations.

Another valuable optimisation method that `dj-tracker` can give hints about is the `.iterator` method. Check out the next steps for more on this.
