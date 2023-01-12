from django.urls import path, re_path

from dj_tracker import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="trackings"),
    path("requests/", views.RequestsView.as_view(), name="requests"),
    re_path(
        r"query-group/(?P<pk>(-?)[0-9]+)/",
        views.QueryGroupView.as_view(),
        name="query-group",
    ),
    re_path(
        r"queryset/(?P<pk>(-?)[0-9]+)/",
        views.QuerysetTrackingView.as_view(),
        name="queryset-tracking",
    ),
    re_path(
        r"(?P<pk>(-?)[0-9]+)/",
        views.URLPathTrackingsView.as_view(),
        name="url-trackings",
    ),
]
