# Tutorial

This tutorial shows how you can use `dj-tracker` to monitor and improve your queries.

We'll take the example of building a page that shows all books of a library.

The source code is available in the [`tutorial` directory](https://github.com/Tijani-Dia/dj-tracker/tree/main/tutorial). The [README](https://github.com/Tijani-Dia/dj-tracker/tree/main/tutorial/README.md) contains instructions to set up the project locally. However, it isn't required and you can just follow along to understand how you might use it in your own project.

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

In a terminal, we create 4000 books to work with:

```console
python manage.py shell -c  "from app.factories import create_books; create_books(4000)"
```

## View - Template

The view that shows all books in the database is defined as follow:

```python
from django.shortcuts import render

from .models import Book


def books_list(request):
    books = Book.objects.all()
    return render(request, "books.html", {"books": books})
```

and this is the corresponding template:

```html
{% for book in books %}
<h4>{{ book.title }}</h4>
<dl>
  <dt>Author</dt>
  <dd>{{ book.author.first_name }} {{ book.author.last_name }}</dd>

  <dt>Category</dt>
  <dd>{{ book.category.name }}</dd>
</dl>
{% endfor %}
```

## URLs

To see how our view performs, we have additional `/time/` and `/memory/` endpoints to track timings and memory usage:

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

- Make 10 requests sequentially to the `/time/` endpoint
- Make 10 requests sequentially to the `/memory/` endpoint
- Make 1 request to the books endpoint with `dj-tracker` running

We run each of these steps in a new process to have consistent results.

Let's now run the first benchmark to see how our view performs:

```shell
Time in ms (10 calls) - Min: 3517.68, Max: 4557.71, Avg: 3964.97

Memory - size in KiB (10 calls) - Min: 38986.07, Max: 39572.61, Avg: 39151.99
Memory - peak in KiB (10 calls) - Min: 41946.51, Max: 42529.80, Avg: 42112.31
```

Our view takes 4s to render and uses around 40Mb in average (in my machine)!

## `dj-tracker` dashboard

Here is how the `dj-tracker` dashboard looks like at this point:

<div style="position: relative; padding-bottom: 56.25%; height: 0;">
    <iframe src="https://www.loom.com/embed/c2b6f0c9990f44d88e27fe944c2931fc" frameborder="0" webkitallowfullscreen mozallowfullscreen allowfullscreen style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></iframe>
</div>

In the [following steps](./detect_and_resolve_related_queries.md), we'll take a closer look at the informations `dj-tracker` gives us to see how we can improve our view.
