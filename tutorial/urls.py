from app.urls import urlpatterns as app_urls
from django.urls import include, path

from dj_tracker.urls import urlpatterns as dj_tracker_urls

urlpatterns = [
    path("", include(app_urls)),
    path("dj-tracker/", include(dj_tracker_urls)),
]
