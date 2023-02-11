from django.shortcuts import render

from .models import Book


def books_list(request):
    only = ("title", "category__name", "author__first_name", "author__last_name")
    context = {
        "books": Book.objects.select_related("author", "category")
        .only(*only)
        .values(*only)
        .iterator()
    }
    return render(request, "books.html", context)
