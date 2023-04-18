# Detect and resolve related queries

In the previous section, we set up a simple view and noticed, after some profiling, that it's particularly slow.

## Detecting related queries

If you didn't see them in the previous step, here are the informations that `dj-tracker` shows for our books query:

![dj-tracker related-queries](../images/related-queries.png)

Apart from the various information on the query itself, we can see that 4000 queries were made via the `author` and `category` fields for our 4000 book instances. In other terms, we're making 2 additional queries for each `Book` instance of our initial queryset a.k.a (2)N + 1. This is very inefficient and the number of queries will keep increasing as we add more `Book` instances.

## Resolving related queries

In our situation, we can use the `select_related` method to fetch all books' authors and categories in a **single** query.

Let's update our view as follows:

```python
def books_list(request):
    books = Book.objects.select_related("author", "category")
    return render(request, "books.html", {"books": books})
```

and run our benchmark:

```shell
Time in ms (10 calls) - Min: 214.51, Max: 292.08, Avg: 251.26

Memory - size in KiB (10 calls) - Min: 35250.04, Max: 35683.38, Avg: 35521.38
Memory - peak in KiB (10 calls) - Min: 38213.27, Max: 38647.72, Avg: 38481.93
```

Our view renders in just 250ms now! That's around 16x speedup compared to our previous version in terms of speed gains. We can also notice that this version uses 5Mb less memory.

Refer to the Django documentation for more information on [`select_related`](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#select-related) and [`prefetch_related`](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#prefetch-related).

## Summary

In the `dj-tracker` dashboard, you can see the latest N+1 situations that were detected.

You can also filter requests by the ones where N+1 queries were detected.

In the query group view, all queries that come from the same field in a queryset are grouped together along with the number of times it happened.

You can then visually tell if you have a N+1 when the number of instances in an initial query is equal to the number of queries that come from a field of the corresponding model.

Depending on the type of the field, you can either use `select_related` or `prefetch_related` to avoid the related queries.

## How it looks?

Here is how the dashboard looks with our new changes:

<div style="position: relative; padding-bottom: 56.25%; height: 0;">
    <iframe src="https://www.loom.com/embed/235ff41baaeb40e280ab446484b66e51" frameborder="0" webkitallowfullscreen mozallowfullscreen allowfullscreen style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></iframe>
</div>

You can see that we no longer have the `Related` section but the number of instances shown is now 12000 representing `4000 Book + 4000 Author + 4000 Category`.

![dj-tracker no-related-queries](../images/no-related-queries.png)

We can click on the query id to have even more information about it (SQL generated, traceback, fields usage...).

The [next steps](./use_only_or_defer.md) will show how we can use those informations to improve our query.
