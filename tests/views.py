from django.shortcuts import render

from tests.models import Book


def books(request):
    return render(request, "tests/books.html", {"books": Book.objects.all()})
