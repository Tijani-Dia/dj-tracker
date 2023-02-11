# Recap

We started with a very slow (1735ms) and memory-consuming (19.5MB) view, applied common optimisations for querysets using the hints and insights `dj-tracker` provides us with then finished with a view that performs reasonably (48ms and 0.15MB).

We can also keep track of the view's performance over time (e.g when we decide that we also want to show a book's summary) in the `dj-tracker` dashboard.

## Closing notes

-   `dj-tracker` can automatically provide these additional hints: [`Use .count`](https://docs.djangoproject.com/en/4.1/topics/db/optimization/#use-queryset-count), [`Use .exists`](https://docs.djangoproject.com/en/4.1/topics/db/optimization/#use-queryset-exists), [`Use .contains`](https://docs.djangoproject.com/en/4.1/topics/db/optimization/#use-queryset-contains-obj)

-   You may not necesarily be able to apply all optimisations we did for our books query, however in many cases, you'll be able to apply some of them.

-   Use the `.iterator` optimisation with caution, ignoring the hint shown in the queryset page if necessary.
