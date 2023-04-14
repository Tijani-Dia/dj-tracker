from collections import Counter
from itertools import takewhile
from operator import itemgetter

from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Prefetch, Sum
from django.db.models.functions import Coalesce
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from dj_tracker.models import Field, InstanceFieldTracking, Query, QueryGroup, Request


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
        context["n_plus_ones"] = QueryGroup.objects.annotate_n_plus_one().filter(
            n_plus_one=True
        )[:5]
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

    def get_query_from_qs_tracking(self, qs_tracking):
        query = qs_tracking.query
        # Copy the values from the QuerySetTracking to the Query for easier access in the template.
        query.duplicate = qs_tracking.duplicate
        query.num_occurrences = qs_tracking.num_occurrences
        return query

    def get_context_data(self, **kwargs):
        qs_trackings = self.object.qs_trackings.select_related(
            "query__model", "query__field__model"
        ).order_by("query__depth")
        queries = {qs_tracking.query_id: qs_tracking for qs_tracking in qs_trackings}
        queries_iter = iter(tuple(queries.values()))

        # Only show queries with depth 0 at the top level; related queries are shown inside their parent.
        root_queries = list(takewhile(lambda x: x.query.depth == 0, queries_iter))
        # To detect similar SQL queries and tracebacks at the top level.
        sqls, tracebacks = Counter(), Counter()
        for query in map(self.get_query_from_qs_tracking, root_queries):
            sqls[query.sql_id] += 1
            tracebacks[query.traceback_id] += 1

        # Workout the related queries.
        for query in map(self.get_query_from_qs_tracking, queries_iter):
            parent_pk = query.related_queryset_id
            try:
                parent = queries[parent_pk]
            except KeyError:
                parent = queries[parent_pk] = query.related_queryset
                parent.from_other_query_group = True
                root_queries.append(parent)

            # Ideally, we would use a defaultdict here, but it causes issues with template rendering.
            if not (related := getattr(parent, "related", None)):
                related = parent.related = {}
            if (field := query.field) not in related:
                related[field] = []

            related[field].append(query)

        context = super().get_context_data(**kwargs)
        context.update(
            # Normalise `queries` to a list of Query objects.
            queries=(getattr(obj, "query", obj) for obj in root_queries),
            similar_sqls=sorted(
                (item for item in sqls.items() if item[1] > 1),
                key=itemgetter(1),
                reverse=True,
            ),
            similar_tracebacks=sorted(
                (item for item in tracebacks.items() if item[1] > 1),
                key=itemgetter(1),
                reverse=True,
            ),
            requests=Request.objects.filter(
                trackings__query_group=self.object
            ).distinct(),
        )
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
