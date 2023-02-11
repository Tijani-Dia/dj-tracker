from django.urls import path

from .profile import MemoryProfiler, TimeProfiler
from .views import books_list

urlpatterns = [
    path("", books_list),
    path("time/", TimeProfiler(books_list)),
    path("memory/", MemoryProfiler(books_list)),
]
