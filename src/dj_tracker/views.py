from collections import Counter, namedtuple
from collections.abc import Mapping
from operator import itemgetter

from django.db.models import Count, Max, Prefetch
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from django_filters import BooleanFilter, FilterSet
from django_filters.views import FilterView

from dj_tracker.cache_utils import lazy_attribute
from dj_tracker.models import InstanceFieldTracking, Query, QueryGroup, Request

OrderByOption = namedtuple("OrderByOption", ["label", "name", "value"])


class OrderByOptions(Mapping):
    def __init__(self, *options):
        self.options = {option.name: option for option in options}

    def __getitem__(self, key):
        return self.options[key]

    def __iter__(self):
        return iter(self.options.values())

    def __len__(self):
        return len(self.options)


class NPlusOneFilter(FilterSet):
    n_plus_one = BooleanFilter(method="filter_n_plus_one", label="N+1")

    def filter_n_plus_one(self, queryset, name, value):
        return queryset.annotate_n_plus_one().filter(n_plus_one=value)


class ListView(FilterView):
    default_per_page = 10
    paginate_by_options = 10, 25, 50, 100

    default_order_by = None
    order_by_options = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.order_by = self.get_active_order_by()
        self.paginate_by = self.get_active_paginate_by()

    def get_active_order_by(self):
        if (order_by := self.request.GET.get("order_by")) not in self.order_by_options:
            order_by = self.default_order_by
        return self.order_by_options[order_by]

    def get_active_paginate_by(self):
        if per_page := self.request.GET.get("per_page"):
            try:
                return int(per_page)
            except ValueError:
                pass

        return self.default_per_page

    def get_queryset(self):
        return self.base_queryset.order_by(self.order_by.value)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            request=self.request,
            active_order_by=self.order_by,
            active_paginate_by=self.paginate_by,
            order_by_options=self.order_by_options,
            paginate_by_options=self.paginate_by_options,
        )
        return context


class HomeView(TemplateView):
    template_name = "dj_tracker/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Requests
        context["most_tracked"] = (
            Request.objects.select_related("path")
            .annotate_num_trackings()
            .order_by("-num_trackings")[:5]
        )
        context["latest"] = (
            Request.objects.alias(latest_tracking=Max("trackings__started_at"))
            .order_by("-latest_tracking")
            .select_related("path")
            .distinct()[:5]
        )

        # Query groups
        context["n_plus_ones"] = (
            QueryGroup.objects.n_plus_one().order_by_latest_occurrence()[:6]
        )
        context["frequent_query_groups"] = (
            QueryGroup.objects.annotate_num_trackings().order_by("-num_trackings")[:5]
        )
        context["largest_query_groups"] = (
            QueryGroup.objects.annotate_num_queries()
            .exclude(trackings__request__path__path="")
            .order_by("-num_queries")[:5]
        )

        # Queries
        context["slowest"] = Query.objects.only("average_duration").order_by(
            "-average_duration"
        )[:5]
        context["largest"] = Query.objects.only("num_instances").order_by(
            "-num_instances"
        )[:5]
        context["most_repeated_queries"] = (
            Query.objects.annotate(num_trackings=Count("trackings", distinct=True))
            .only("cache_key")
            .order_by("-num_trackings")[:5]
        )
        return context


class RequestsView(ListView):
    template_name = "dj_tracker/requests.html"

    default_order_by = "-date"
    order_by_options = OrderByOptions(
        OrderByOption("Date (latest)", "-date", "-latest_occurrence"),
        OrderByOption("Date (earliest)", "date", "latest_occurrence"),
        OrderByOption("Occurrence (ascending)", "occurrence", "num_trackings"),
        OrderByOption("Occurrence (descending)", "-occurrence", "-num_trackings"),
        OrderByOption("Path (A -> Z)", "path", "path__path"),
        OrderByOption("Path (Z -> A)", "-path", "-path__path"),
    )

    filterset_class = NPlusOneFilter

    @lazy_attribute
    def base_queryset(cls):
        return (
            Request.objects.select_related("path")
            .annotate_num_trackings()
            .annotate_latest_occurrence()
        )


class QueryGroupsView(ListView):
    template_name = "dj_tracker/query_groups.html"

    default_order_by = "-date"
    order_by_options = OrderByOptions(
        OrderByOption("Date (latest)", "-date", "-latest_occurrence"),
        OrderByOption("Date (earliest)", "date", "latest_occurrence"),
        OrderByOption("Occurrence (ascending)", "occurrence", "num_trackings"),
        OrderByOption("Occurrence (descending)", "-occurrence", "-num_trackings"),
        OrderByOption("Number of queries (ascending)", "num_queries", "num_queries"),
        OrderByOption("Number of queries (descending)", "-num_queries", "-num_queries"),
    )

    filterset_class = NPlusOneFilter

    def setup(self, request, *args, request_id=None, **kwargs):
        super().setup(request, *args, **kwargs)
        self.request_obj = (
            get_object_or_404(Request.objects.select_related("path"), pk=request_id)
            if request_id
            else None
        )

    @lazy_attribute
    def base_queryset(cls):
        return (
            QueryGroup.objects.annotate_num_queries()
            .annotate_num_trackings()
            .annotate_latest_occurrence()
        )

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request_obj:
            qs = qs.filter(trackings__request=self.request_obj)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.request_obj or "Query groups"
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
        qs_trackings = self.object.querysettracking_set.select_related(
            "query__model", "query__field__model"
        ).order_by("query__depth")
        queries = {qs_tracking.query_id: qs_tracking for qs_tracking in qs_trackings}

        root_queries = []
        sqls = Counter()
        tracebacks = Counter()
        for query in map(self.get_query_from_qs_tracking, qs_trackings):
            if query.depth > 0:
                # Only show queries with depth 0 at the top level;
                # related queries are shown inside their parent.
                break

            root_queries.append(query)
            sqls[query.sql_id] += 1
            tracebacks[query.traceback_id] += 1

        # Workout the related queries.
        for query in map(
            self.get_query_from_qs_tracking, qs_trackings[len(root_queries) :]
        ):
            parent_pk = query.related_queryset_id
            try:
                parent = queries[parent_pk]
            except KeyError:
                parent = queries[parent_pk] = query.related_queryset
                parent.from_other_query_group = True
                root_queries.append(parent)
            else:
                parent = getattr(parent, "query", parent)

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


class QueriesView(ListView):
    template_name = "dj_tracker/queries.html"

    default_order_by = "-duration"
    order_by_options = OrderByOptions(
        OrderByOption("Duration (ascending)", "duration", "average_duration"),
        OrderByOption("Duration (descending)", "-duration", "-average_duration"),
        OrderByOption("Occurrence (ascending)", "occurrence", "num_trackings"),
        OrderByOption("Occurrence (descending)", "-occurrence", "-num_trackings"),
        OrderByOption(
            "Number of instances (ascending)", "num_instances", "num_instances"
        ),
        OrderByOption(
            "Number of instances (descending)", "-num_instances", "-num_instances"
        ),
    )

    model = Query
    filterset_fields = ["model", "query_type"]

    @lazy_attribute
    def base_queryset(cls):
        return (
            Query.objects.annotate(num_trackings=Count("trackings", distinct=True))
            .select_related("sql", "model")
            .only(
                "query_type",
                "num_instances",
                "average_duration",
                "sql__sql",
                "model__label",
            )
        )


class QueryView(DetailView):
    template_name = "dj_tracker/query.html"

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
