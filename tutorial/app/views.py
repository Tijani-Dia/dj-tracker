from django.db.models import CharField, F, Value
from django.db.models.functions import Concat
from django.shortcuts import render

from .models import Book


def books_list(request):
    books = Book.objects.values(
        "title",
        category_name=F("category__name"),
        author_full_name=Concat(
            "author__first_name",
            Value(" "),
            "author__last_name",
            output_field=CharField(),
        ),
    ).iterator()
    return render(request, "books.html", {"books": books})
