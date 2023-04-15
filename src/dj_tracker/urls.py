from django.urls import path, register_converter

from dj_tracker import views


class CacheKeyConverter:
    regex = r"(-?)[0-9]+"

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


register_converter(CacheKeyConverter, "cache_key")

urlpatterns = [
    path("", views.HomeView.as_view(), name="trackings"),
    path("queries/", views.QueriesView.as_view(), name="queries"),
    path("requests/", views.RequestsView.as_view(), name="requests"),
    path("query-groups/", views.QueryGroupsView.as_view(), name="query-groups"),
    path(
        "query/<cache_key:pk>/",
        views.QueryView.as_view(),
        name="query",
    ),
    path(
        "query-groups/<cache_key:request_id>/",
        views.QueryGroupsView.as_view(),
        name="request",
    ),
    path(
        "query-group/<cache_key:pk>/",
        views.QueryGroupView.as_view(),
        name="query-group",
    ),
]
