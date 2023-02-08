from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Prefetch, Sum
from django.db.models.functions import Coalesce
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from dj_tracker.models import (
    Field,
    InstanceFieldTracking,
    Query,
    QueryGroup,
    QuerySetTracking,
    Request,
)


class HomeView(TemplateView):
    template_name = "dj_tracker/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["most_tracked"] = (
            Request.objects.select_related("path")
            .annotate(num_trackings=Count("trackings"))
            .order_by("-num_trackings")[:5]
        )
        context["latest"] = (
            Request.objects.alias(latest_tracking=Max("trackings__started_at"))
            .order_by("-latest_tracking")
            .select_related("path")
            .distinct()[:5]
        )
        context["most_accessed_fields"] = (
            Field.objects.annotate(get_count=Coalesce(Sum("trackings__get_count"), 0))
            .annotate(set_count=Coalesce(Sum("trackings__set_count"), 0))
            .alias(access_count=F("get_count") + F("set_count"))
            .order_by("-access_count")
            .select_related("model")[:10]
        )
        context["slowest"] = Query.objects.only(
            "cache_key", "average_duration"
        ).order_by("-average_duration")[:5]
        context["most_repeated_queries"] = Query.objects.annotate(
            num_trackings=Count("trackings")
        ).order_by("-num_trackings")[:5]
        context["largest_query_groups"] = (
            QueryGroup.objects.annotate_num_queries()
            .exclude(trackings__request__path__path="")
            .order_by("-num_queries")[:5]
        )
        return context


class RequestsView(ListView):
    template_name = "dj_tracker/requests.html"
    paginate_by = 10

    def get_queryset(self):
        return (
            Request.objects.select_related("path")
            .annotate(num_trackings=Count("trackings"))
            .order_by("-num_trackings")
        )


class URLPathTrackingsView(DetailView):
    template_name = "dj_tracker/url_trackings.html"
    model = Request

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query_groups = (
            QueryGroup.objects.annotate_num_queries()
            .filter(trackings__request_id=self.object.pk)
            .annotate(
                num_trackings=Count("trackings"),
                latest_run_at=Max("trackings__started_at"),
            )
            .order_by("-latest_run_at")
        )
        context["page_obj"] = Paginator(query_groups, 7).get_page(
            self.request.GET.get("page")
        )
        return context


class QueryGroupView(DetailView):
    template_name = "dj_tracker/query_group.html"

    def get_queryset(self):
        return QueryGroup.objects.annotate_num_queries()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.object.pk
        context["requests"] = Request.objects.filter(
            trackings__query_group_id=pk
        ).distinct()

        qs_trackings = (
            QuerySetTracking.objects.filter(query_group_id=self.object.pk)
            .select_related("query__model", "query__field__model")
            .iterator()
        )
        trackings = {obj.query_id: obj for obj in qs_trackings}
        pks = []
        for tracking in trackings.values():
            query = tracking.query
            if not (parent_pk := query.related_queryset_id):
                pks.append(str(query.pk))
                continue

            # May raise KeyError.
            # Can happen when the related queryset comes from another request.
            parent = trackings[parent_pk]
            if not (related := getattr(parent, "related", None)):
                related = parent.related = {}
            if (field := query.field) not in related:
                related[field] = []
            related[field].append(tracking)

        context["qs_trackings"] = (
            tracking for tracking in trackings.values() if tracking.query.depth == 0
        )
        context["query_pks"] = pks
        return context


class QuerysetTrackingView(DetailView):
    template_name = "dj_tracker/queryset_tracking.html"

    def get_queryset(self):
        prefetch_instance_trackings = Prefetch(
            "instance_trackings__related_field_trackings",
            queryset=InstanceFieldTracking.objects.select_related(
                "field_tracking__field"
            ).order_by("-field_tracking__get_count", "-field_tracking__set_count"),
        )
        return Query.objects.select_related(
            "sql", "traceback__template_info__filename"
        ).prefetch_related(prefetch_instance_trackings)
