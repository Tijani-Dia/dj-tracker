from django.db import models
from django.urls import reverse


class QueryType(models.TextChoices):
    COUNT = "COUNT"
    SELECT = "SELECT"
    EXISTS = "EXISTS"


class Promisable(models.Model):
    """
    A Promisable is a model whose instances' primary keys (`cache_key`)
    are deduced from the data they hold.
    """

    cache_key = models.BigIntegerField(primary_key=True)

    class Meta:
        abstract = True


class Model(Promisable):
    label = models.CharField(max_length=255)

    def __str__(self):
        return self.label


class Field(Promisable):
    model = models.ForeignKey(Model, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} ({self.model})"


class SQL(Promisable):
    sql = models.TextField()

    def __str__(self):
        return self.sql


class URLPath(Promisable):
    path = models.CharField(max_length=1024)

    def __str__(self):
        return self.path


class Request(Promisable):
    path = models.ForeignKey(URLPath, on_delete=models.CASCADE, related_name="requests")
    method = models.CharField(max_length=8)
    content_type = models.CharField(max_length=256)
    query_string = models.CharField(max_length=1024)

    def get_absolute_url(self):
        return reverse("url-trackings", kwargs={"pk": self.pk})

    def __str__(self):
        if not self.method:
            return "DummyRequest"

        base = f"[{self.method}] {self.path}"
        return base if not self.query_string else f"{base}?{self.query_string}"


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


class Traceback(Promisable):
    stack = models.ManyToManyField(SourceCode, through="StackEntry", related_name="+")
    template_info = models.ForeignKey(SourceCode, on_delete=models.CASCADE, null=True)

    def entries(self):
        return (
            SourceCode.objects.filter(entries__traceback_id=self.pk)
            .select_related("filename")
            .order_by("entries__index")
        )


class StackEntry(models.Model):
    traceback = models.ForeignKey(Traceback, on_delete=models.CASCADE)
    source = models.ForeignKey(
        SourceCode, on_delete=models.CASCADE, related_name="entries"
    )
    index = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ("index",)


class FieldTracking(Promisable):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="trackings")
    get_count = models.PositiveIntegerField(default=0)
    set_count = models.PositiveIntegerField(default=0)

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
    average_duration = models.PositiveIntegerField(null=True)
    cache_hits = models.PositiveSmallIntegerField(null=True)
    iterable_class = models.CharField(blank=True, max_length=64)
    query_type = models.CharField(choices=QueryType.choices, max_length=6)
    depth = models.PositiveSmallIntegerField(default=0)
    attributes_accessed = models.JSONField(null=True)
    len_calls = models.PositiveSmallIntegerField(null=True)
    exists_calls = models.PositiveSmallIntegerField(null=True)
    contains_calls = models.PositiveSmallIntegerField(null=True)
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
        if self.query_type != QueryType.SELECT:
            return

        cache_hits = self.cache_hits
        if self.len_calls and cache_hits == 2 * self.len_calls - 1:
            yield "Use .count()"
        elif self.exists_calls and cache_hits == 2 * self.exists_calls:
            yield "Use .exists()"
        elif self.contains_calls and cache_hits == 2 * self.contains_calls:
            yield "Use .contains()"

        if self.num_instances == 0:
            return

        if cache_hits == 1:
            yield "Use .iterator()"
        if (
            (attrs_accessed := self.attributes_accessed) is not None
            and len(attrs_accessed) <= 3
            and set(attrs_accessed).issubset({"__dict__", "__class__", "_state"})
        ):
            yield "Use .values() or .values_list()"

    @property
    def average_duration_in_ms(self):
        return round(self.average_duration * 1e-6, 2)


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
