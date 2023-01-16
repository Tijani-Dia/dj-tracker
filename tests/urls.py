from django.urls import include, path

from dj_tracker.urls import urlpatterns as dj_tracker_urls
from tests import views

urlpatterns = [
    path("books/", views.books, name="books"),
    path("dj-tracker/", include(dj_tracker_urls)),
]
