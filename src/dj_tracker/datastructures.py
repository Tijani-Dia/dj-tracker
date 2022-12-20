import collections.abc
import functools
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import chain
from weakref import finalize as weakref_finalize
from weakref import ref as weak_reference

from django.db import models
from django.http import HttpRequest
from django.utils.timezone import now

from dj_tracker.collector import Collector
from dj_tracker.constants import DUMMY_REQUEST
from dj_tracker.context import get_request
from dj_tracker.promise import (
    FieldPromise,
    FieldTrackingPromise,
    InstanceTrackingPromise,
    ModelPromise,
    QueryPromise,
    SQLPromise,
    TracebackPromise,
)
from dj_tracker.utils import get_sql_from_query


class TrackedObject:
    __slots__ = ("tracked", "_tracker", "__weakref__")

    def __init__(self, initial, tracker):
        self.tracked = initial
        self._tracker = tracker

    def __len__(self):
        return len(self.tracked)

    def __repr__(self):
        return repr(self.tracked)


class TrackedDict(TrackedObject, collections.abc.MutableMapping):
    __slots__ = ()

    def __getitem__(self, name):
        try:
            value = dict.__getitem__(self.tracked, name)
        except KeyError:
            raise
        else:
            self._tracker[name].get += 1
            return value

    def __setitem__(self, key, value):
        dict.__setitem__(self.tracked, key, value)

    def __delitem__(self, key):
        dict.__delitem__(self.tracked, key)

    def __iter__(self):
        return iter(self.tracked)


class TrackedSequence(TrackedObject, collections.abc.Sequence):
    __slots__ = ()

    def __getitem__(self, index):
        try:
            value = self.tracked.__getitem__(index)
        except IndexError:
            raise
        else:
            if type(index) is int:
                self._tracker[str(index)].get += 1
            else:
                for i in range(
                    index.start if index.start is not None else 0,
                    index.stop if index.stop is not None else len(self.tracked),
                    index.step if index.step else 1,
                ):
                    self._tracker[str(i)].get += 1
            return value

    def __eq__(self, other):
        return other == self.tracked

    def __hash__(self):
        return hash(self.tracked)


class TrackedResultCache(TrackedObject, collections.abc.Sequence):
    __slots__ = ()

    def __init__(self, initial, tracker):
        super().__init__(initial, tracker)
        weakref_finalize(self, self._tracker.result_cache_collected)

    def __getitem__(self, index):
        return self.tracked.__getitem__(index)

    def __len__(self):
        self._tracker.len_calls += 1
        return len(self.tracked)

    def __contains__(self, value):
        self._tracker.contains_calls += 1
        return value in self.tracked

    def __bool__(self):
        self._tracker.exists_calls += 1
        return bool(self.tracked)


class FieldTracker:
    __slots__ = ("get", "set")

    def __init__(self, get=0, set=0):
        self.get = get
        self.set = set

    def __hash__(self):
        return hash((self.get, self.set))

    def __eq__(self, other):
        return (
            type(other) is FieldTracker
            and self.get == other.get
            and self.set == other.set
        )

    def __repr__(self):
        return f"FieldTracker(get={self.get}, set={self.set})"


class InstanceTracker(dict):
    __slots__ = ("queryset", "object", "related")

    def __getstate__(self):
        return {
            "values": dict(self),
            "queryset": self.queryset,
            "object": self.object() if hasattr(self, "object") else None,
        }

    def __setstate__(self, state):
        self.update(state["values"])
        self.queryset = state["queryset"]
        self.object = weak_reference(state["object"]) if state["object"] else None

    def add_related_instance(self, instance, field, related_model):
        if not (related := getattr(self, "related", None)):
            self.related = related = defaultdict(list)
        related[(field, related_model)].append(instance)


class RequestTracker:
    __slots__ = (
        "path",
        "method",
        "content_type",
        "query_string",
        "started_at",
        "queries",
        "num_queries",
        "collected",
    )

    def __init__(self, request):
        self.path = request.path
        self.method = request.method
        self.content_type = request.content_type
        self.query_string = request.META.get("QUERY_STRING", "")
        self.started_at = now()
        self.queries = []
        self.num_queries = 0
        self.collected = False
        weakref_finalize(request, self.request_collected)
        Collector.add_request(self)

    def add_query(self, query_id, duration):
        self.queries.append((query_id, duration))
        if self.ready:
            Collector.request_ready(self)

    def request_collected(self):
        self.collected = True
        if self.ready:
            Collector.request_ready(self)

    @property
    def ready(self):
        return self.num_queries == len(self.queries) and self.collected


class QuerySetTracker:
    promise_kwargs = (
        "depth",
        "query_type",
        "cache_hits",
        "num_instances",
        "iterable_class",
        "instance_trackings",
        "attributes_accessed",
        "len_calls",
        "exists_calls",
        "contains_calls",
        "sql_id",
        "field_id",
        "model_id",
        "traceback_id",
        "related_queryset_id",
    )

    __slots__ = promise_kwargs + (
        "duration",
        "num_ready",
        "num_trackers",
        "request_tracker",
        "deferred_fields",
        "related_querysets",
        "instance_trackers",
        "_iter_done",
        "_attributes_accessed",
        "_result_cache_collected",
    )

    def __init__(
        self,
        queryset,
        query_type,
        check_accessed_instances=False,
        result_cache_collected=False,
        iterable_class="",
    ):
        self.traceback_id = TracebackPromise.get()
        self.model_id = ModelPromise.get_or_create(label=queryset.model._meta.label)
        self.field_id = self.related_queryset_id = None
        self.request_tracker = get_tracker(get_request())
        self.query_type = query_type
        self.iterable_class = iterable_class
        self._result_cache_collected = result_cache_collected
        if check_accessed_instances:
            self._attributes_accessed = Counter()

        self._iter_done = False
        self.cache_hits = None
        self.depth = 0
        self.len_calls = self.exists_calls = self.contains_calls = 0
        self.num_instances = self.num_trackers = self.num_ready = 0
        self.related_querysets = []
        self.instance_trackers = defaultdict(list)
        self.deferred_fields = defaultdict(set)

        if (instance := queryset._hints.get("instance")) and (
            instance_tracker := getattr(instance, "_tracker", None)
        ):
            instance_tracker.queryset.add_related_queryset(self)
            if field := queryset._hints.get("field"):
                self.set_field(field, type(instance))

        queryset._tracker = self

    def add_related_queryset(self, qs_tracker):
        self.related_querysets.append(qs_tracker)
        qs_tracker.related_queryset_id = self
        qs_tracker.depth = self.depth + 1

    def add_deferred_field(self, field, instance):
        self.deferred_fields[field].add(instance)

    def set_field(self, field, model):
        self.field_id = FieldPromise.get_or_create(
            model_id=ModelPromise.get_or_create(label=model._meta.label), name=field
        )

    def track_instance(self, instance, model, field=""):
        instance, tracker = get_tracker(instance)
        if not tracker:
            return instance

        tracker.queryset = self
        self.instance_trackers[(field, model)].append(tracker)
        self.num_trackers += 1
        weakref_finalize(instance, self.instance_tracker_ready)

        if related := getattr(tracker, "related", None):
            track = self.track_instance
            for (
                related_field,
                related_model,
            ), related_instances in related.items():
                field_label = (
                    related_field if not field else f"{field}__{related_field}"
                )
                for related_instance in related_instances:
                    track(related_instance, related_model, field_label)

            del tracker.related

        return instance

    @property
    def ready(self):
        return (
            self.num_ready == self.num_trackers
            and self._iter_done
            and self._result_cache_collected
        )

    def instance_tracker_ready(self):
        self.num_ready += 1
        if self.ready:
            Collector.tracker_ready(self)

    def result_cache_collected(self):
        self._result_cache_collected = True
        if self.ready:
            Collector.tracker_ready(self)

    def iter_done(self, queryset, duration):
        self.sql_id = SQLPromise.get_or_create(sql=get_sql_from_query(queryset.query))
        self.duration = timedelta(microseconds=duration * 10e-3)
        self._iter_done = True

        if not (related_qs := self.related_queryset_id):
            Collector.add_tracker(self)
        elif self.num_instances == 1 and (
            deferred_fields := related_qs.deferred_fields
        ):
            instance = queryset._hints["instance"]
            db_instance = self.instance_trackers[("", queryset.model)][0].object()
            if type(instance) is type(db_instance) and instance.pk == db_instance.pk:
                loaded_fields = tuple(
                    field for field in deferred_fields if field in db_instance.__dict__
                )
                if (
                    len(loaded_fields) == 1
                    and instance in deferred_fields[loaded_fields[0]]
                ):
                    self.set_field(loaded_fields[0], queryset.model)
                    deferred_fields[loaded_fields[0]].remove(instance)

    def _set_extra_attributes(self):
        all_fields = set()
        instance_trackings = []

        for (select_related_field, model), trackers in self.instance_trackers.items():
            fields = {}
            model_id = ModelPromise.get_or_create(label=model._meta.label)

            for field, field_tracker in chain.from_iterable(
                tracker.items() for tracker in trackers
            ):
                if not (field_data := fields.get(field)):
                    fields[field] = field_data = (
                        FieldPromise.get_or_create(model_id=model_id, name=field),
                        Counter(),
                    )
                field_data[1][field_tracker] += 1

            objs = chain.from_iterable(
                (
                    (
                        FieldTrackingPromise.get_or_create(
                            field_id=field_id,
                            get_count=field_tracker.get,
                            set_count=field_tracker.set,
                        ),
                        num_occurrences,
                    )
                    for field_tracker, num_occurrences in field_trackings.items()
                )
                for field_id, field_trackings in fields.values()
            )

            instance_trackings.append(
                InstanceTrackingPromise.get_or_create(
                    field_trackings=tuple(objs),
                    select_related_field=select_related_field,
                )
            )
            all_fields.update(fields)

        if attributes_accessed := getattr(self, "_attributes_accessed", None):
            attributes_accessed.pop("_tracker", None)
            attributes_accessed = {
                attr: access_count
                for attr, access_count in attributes_accessed.items()
                if attr not in all_fields and access_count
            }

        self.instance_trackings = tuple(instance_trackings)
        self.attributes_accessed = attributes_accessed

    def save(self):
        self._set_extra_attributes()
        query_id = QueryPromise.get_or_create(
            **{attr: getattr(self, attr) for attr in self.promise_kwargs}
        )

        for related_tracker in self.related_querysets:
            related_tracker.related_queryset_id = query_id
            Collector.add_tracker(related_tracker)

        self.request_tracker.add_query(query_id, self.duration)
        return query_id


@functools.singledispatch
def get_tracker(instance):
    return instance, None


@get_tracker.register(models.Model)
def _(instance):
    tracker = instance._tracker
    tracker.object = weak_reference(instance)
    return instance, tracker


@get_tracker.register(dict)
def _(instance):
    tracker = InstanceTracker({field: FieldTracker() for field in instance})
    return TrackedDict(instance, tracker), tracker


@get_tracker.register(tuple)
@get_tracker.register(list)
def _(instance):
    tracker = InstanceTracker({str(i): FieldTracker() for i in range(len(instance))})
    return TrackedSequence(instance, tracker), tracker


@get_tracker.register(HttpRequest)
@get_tracker.register(type(DUMMY_REQUEST))
def _(instance):
    if not (tracker := getattr(instance, "_tracker", None)):
        tracker = instance._tracker = RequestTracker(instance)

    tracker.num_queries += 1
    return tracker
