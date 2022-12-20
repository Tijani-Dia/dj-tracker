from itertools import groupby
from operator import attrgetter

from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

from dj_tracker.promise import Promisable


class QueryType(models.TextChoices):
    COUNT = "COUNT"
    SELECT = "SELECT"
    EXISTS = "EXISTS"


class IterableClass(models.TextChoices):
    MODEL = "ModelIterable"
    VALUES = "ValuesIterable"
    VALUES_LIST = "ValuesListIterable"
    FLAT_VALUES_LIST = "FlatValuesListIterable"
    NAMED_VALUES_LIST = "NamedValuesListIterable"


class Model(Promisable):
    label = models.CharField(max_length=255)

    def __str__(self):
        return self.label


class Field(Promisable):
    model = models.ForeignKey(Model, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.model}.{self.name}"


class SQL(Promisable):
    sql = models.TextField()

    def __str__(self):
        return self.sql


class URLPath(Promisable):
    path = models.CharField(max_length=1024)

    def __str__(self):
        return self.path

    def get_absolute_url(self):
        return reverse("url-trackings", kwargs={"pk": self.pk})


class Request(Promisable):
    path = models.ForeignKey(URLPath, on_delete=models.CASCADE, related_name="requests")
    method = models.CharField(max_length=8)
    content_type = models.CharField(max_length=256)
    query_string = models.CharField(max_length=1024)


class SourceFile(Promisable):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class SourceCode(Promisable):
    filename = models.ForeignKey(SourceFile, on_delete=models.CASCADE)
    lineno = models.PositiveIntegerField()
    code = models.TextField()
    func = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.filename} - {self.func}:{self.lineno}"


class Stack(Promisable):
    entries = models.ManyToManyField(SourceCode, through="StackEntry")


class StackEntry(models.Model):
    stack = models.ForeignKey(Stack, on_delete=models.CASCADE)
    source = models.ForeignKey(SourceCode, on_delete=models.CASCADE)
    index = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ("index",)


class Traceback(Promisable):
    top = models.ForeignKey(Stack, on_delete=models.CASCADE, related_name="+")
    middle = models.ForeignKey(Stack, on_delete=models.CASCADE, related_name="+")
    bottom = models.ForeignKey(Stack, on_delete=models.CASCADE, related_name="+")
    template_info = models.ForeignKey(SourceCode, on_delete=models.CASCADE, null=True)

    @cached_property
    def entries(self):
        entries = (
            StackEntry.objects.select_related("source__filename")
            .filter(stack_id__in=(self.top_id, self.middle_id, self.bottom_id))
            .order_by("stack_id", "index")
            .iterator()
        )
        keys_map = {
            self.top_id: "top",
            self.middle_id: "middle",
            self.bottom_id: "bottom",
        }
        return {
            keys_map[stack_id]: tuple(entry.source for entry in entries)
            for stack_id, entries in groupby(entries, attrgetter("stack_id"))
        }


class FieldTracking(Promisable):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="trackings")
    get_count = models.PositiveIntegerField()
    set_count = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.field}: Get: {self.get_count}, Set: {self.set_count}"


class InstanceTracking(Promisable):
    field_trackings = models.ManyToManyField(
        FieldTracking, through="InstanceFieldTracking"
    )
    select_related_field = models.CharField(max_length=255, blank=True)


class InstanceFieldTracking(models.Model):
    instance_tracking = models.ForeignKey(
        InstanceTracking,
        on_delete=models.CASCADE,
        related_name="related_field_trackings",
    )
    field_tracking = models.ForeignKey(FieldTracking, on_delete=models.CASCADE)
    num_occurrences = models.PositiveIntegerField()


class Query(Promisable):
    sql = models.ForeignKey(SQL, on_delete=models.CASCADE)
    model = models.ForeignKey(Model, on_delete=models.CASCADE)
    traceback = models.ForeignKey(Traceback, on_delete=models.CASCADE)
    cache_hits = models.PositiveSmallIntegerField(null=True)
    iterable_class = models.CharField(
        max_length=24, choices=IterableClass.choices, blank=True
    )
    query_type = models.CharField(choices=QueryType.choices, max_length=6)
    depth = models.PositiveSmallIntegerField()
    attributes_accessed = models.JSONField(null=True)
    len_calls = models.PositiveSmallIntegerField()
    exists_calls = models.PositiveSmallIntegerField()
    contains_calls = models.PositiveSmallIntegerField()
    num_instances = models.PositiveIntegerField()
    instance_trackings = models.ManyToManyField(InstanceTracking)
    field = models.ForeignKey(Field, on_delete=models.CASCADE, null=True)
    related_queryset = models.ForeignKey(
        "self",
        null=True,
        on_delete=models.CASCADE,
        related_name="related_querysets",
    )

    def get_absolute_url(self):
        return reverse("queryset-tracking", kwargs={"pk": self.pk})

    def get_hints(self):
        cache_hits = self.cache_hits
        if cache_hits == 1:
            yield "Use .iterator()"
        if cache_hits == 2 * self.len_calls - 1:
            yield "Use .count()"
        elif cache_hits == 2 * self.exists_calls:
            yield "Use .exists()"
        elif cache_hits == 2 * self.contains_calls:
            yield "Use .contains()"
        if self.attributes_accessed == {}:
            yield "Use .values() or .values_list()"


class QueryGroupManager(models.Manager):
    def annotate_num_queries(self):
        # https://stackoverflow.com/questions/52027676/using-subquery-to-annotate-a-count
        num_queries = (
            QuerySetTracking.objects.filter(query_group_id=models.OuterRef("pk"))
            .order_by()
            .annotate(total=models.Func(models.F("num_occurrences"), function="Sum"))
            .values("total")
        )
        return self.annotate(num_queries=models.Subquery(num_queries))


class QueryGroup(Promisable):
    queries = models.ManyToManyField(Query, through="QuerySetTracking")
    objects = QueryGroupManager()

    def get_absolute_url(self):
        return reverse("query-group", kwargs={"pk": self.pk})


class QuerySetTracking(models.Model):
    query = models.ForeignKey(Query, on_delete=models.CASCADE, related_name="trackings")
    query_group = models.ForeignKey(QueryGroup, on_delete=models.CASCADE)
    # Number of occurrences of query in query_group.
    num_occurrences = models.PositiveSmallIntegerField()
    # Average duration of query in this group.
    average_duration = models.DurationField()

    def get_absolute_url(self):
        return self.query.get_absolute_url()

    def duplicate(self):
        return self.num_occurrences > 1


class Tracking(models.Model):
    started_at = models.DateTimeField()
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="trackings"
    )
    query_group = models.ForeignKey(
        QueryGroup, on_delete=models.CASCADE, related_name="trackings"
    )

    class Meta:
        ordering = ("-started_at",)

    def get_absolute_url(self):
        return reverse("tracking", kwargs={"pk": self.pk})
