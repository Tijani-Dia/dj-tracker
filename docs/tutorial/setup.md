# Tutorial

This tutorial shows how you can use `dj-tracker` to monitor and improve your queries.

We'll take the example of building a page that shows all books of a library.

The source code is available in the [`tutorial` directory](https://github.com/Tijani-Dia/dj-tracker/tree/main/tutorial). You can check out the steps in the [README](https://github.com/Tijani-Dia/dj-tracker/tree/main/tutorial/README.md) to set up the project locally. However, it isn't required and you can just follow along to understand how you might use it in your own project.

## Models

We'll work with the following models:

```python
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=64)


class Author(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    date_of_birth = models.DateTimeField()
    date_of_death = models.DateTimeField(null=True, blank=True)
    biography = models.TextField()


class Book(models.Model):
    title = models.CharField(max_length=255)
    summary = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
```

We also define some factories to build `Book` instances to work with:

```python
import factory

from .models import Author, Book, Category


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Faker("word")


class AuthorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Author

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")
    date_of_death = factory.Faker("date_time_this_century")
    biography = factory.Faker("text", max_nb_chars=5000)


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book

    title = factory.Faker("sentence")
    summary = factory.Faker("text", max_nb_chars=2500)
    author = factory.SubFactory(AuthorFactory)
    category = factory.SubFactory(CategoryFactory)


create_books = BookFactory.create_batch
```

Keep in mind how we set a large content for the `summary` and `biography` fields.

In a terminal, we create 2000 books to work with:

```console
python manage.py shell -c  "from app.factories import create_books; create_books(2000)"
```

## View - Template

We define the view that shows all books in the database:

```python
from django.shortcuts import render

from .models import Book


def books_list(request):
    return render(
        request,
        "books.html",
        {"books": Book.objects.all()}
    )
```

and the template to use:

```html
{% for book in books %}
    {{ book.title }} -({{ book.author.first_name }} {{book.author.last_name }}) - {{ book category }}
{% endfor %}
```

## URLs

To see how our view performs, we have `/time/` and `/memory/` endpoints to track timings and memory usage:

```python
from django.urls import path

from .profile import MemoryProfiler, TimeProfiler
from .views import books_list

urlpatterns = [
    path("", books_list),
    path("time/", TimeProfiler(books_list)),
    path("memory/", MemoryProfiler(books_list)),
]
```

## Profiling

We'll use the following methodology to profile the view:

-   Make 25 requests to the `/time/` endpoint
-   Make 25 requests to the `/memory/` endpoint
-   Make 1 request to the books endpoint with `dj-tracker` running

We run each of these steps in a new process to have consistent results.

## Results

We can now run our first benchmark. Here are the results:

```shell
Time in ms (25 calls) - Min: 1680.77, Max: 1975.24, Avg: 1735.77

Memory - size in KiB (25 calls) - Min: 19477.24, Max: 19855.44, Avg: 19579.39
Memory - peak in KiB (25 calls) - Min: 20624.29, Max: 21003.30, Avg: 20726.55
```

Our view takes up to 2s to render and uses around 20Mb in average (in my machine)!

## `dj-tracker`

Here is what we can see at the `/dj-tracker/` endpoint:

![dj-tracker Dashboard](../images/tuto-1.gif)

In the following steps, we'll see how `dj-tracker` can help us detect why our view is slow and ways to improve it.
