# `values`/`values_list` usage

When `dj-tracker` detects that no model attributes/methods, except the ones needed to build model instances, are used for all instances of a queryset; it'll hint at using the [`.values` or `.values_list`](https://docs.djangoproject.com/en/4.1/topics/db/optimization/#use-queryset-values-and-values-list) methods.

In our example, we're only using raw model fields, namely `title`, `category.name`, `author.first_name` and `author.last_name`; we aren't using any method or such. Therefore it's a candidate for the `Use values/values_list` hint:

![dj-tracker Use values/values_list](../images/use-values-list.png)

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

Our query will now return dictionary objects instead of model instances. An instance will have the following structure:

```python
{
    "title": "Harry Potter",
    "category__name": "Science Fiction",
    "author__first_name": "Joanne",
    "author__last_name": "Rowling"
}
```

Let's update our template to match this new structure:

```html
{% for book in books %}
    {{ book.title }} -({{ book.author__first_name }} {{book.author__last_name }}) - {{ book.category__name }}
{% endfor %}
```

## Profile

Let's now run our profilers to see how our view performs:

```console
Time in ms (25 calls) - Min: 40.05, Max: 72.93, Avg: 47.13

Memory - size in KiB (25 calls) - Min: 1008.73, Max: 1154.21, Avg: 1030.85
Memory - peak in KiB (25 calls) - Min: 2156.58, Max: 2302.35, Avg: 2178.71
```

Our new version is in average 2.5x faster (previous average was 115.76ms) and uses 2.7x less memory as well.

This can be explained by the fact that creating and manipulating dictionaries is cheaper than doing the same with model instances - both in speed and in memory terms.

This is now what the field stats for our query look like:

![dj-tracker - Field stats](../images/field-stats-3.png)

## Summary

`dj-tracker` keeps track of every model atribute/method access to provide hints on when to use the [`.values`](https://docs.djangoproject.com/en/4.0/ref/models/querysets/#values) or [`.values_list`](https://docs.djangoproject.com/en/4.0/ref/models/querysets/#values-list) optimisations.

Another valuable optimisation method that `dj-tracker` can give hints about is the `.iterator` method. Check out the [next steps](./use_iterator.md) for more on this.
