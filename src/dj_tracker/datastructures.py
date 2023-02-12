import collections.abc
import functools
import uuid
import weakref
from collections import Counter, defaultdict, deque
from itertools import chain

from django.db import transaction
from django.utils.timezone import now

from dj_tracker.cache_utils import LazySlots, cached_attribute
from dj_tracker.collector import Collector
from dj_tracker.constants import DUMMY_REQUEST, TRACKINGS_DB
from dj_tracker.context import get_request
from dj_tracker.hash_utils import HashableCounter, HashableMixin
from dj_tracker.models import QueryGroup, QuerySetTracking, Tracking
from dj_tracker.promise import QueryGroupPromise, QueryPromise, RequestPromise
from dj_tracker.traceback import get_traceback

weak_reference = weakref.ref
weakref_finalize = weakref.finalize


class TrackedObject:
    __slots__ = ("tracked", "_tracker", "__weakref__")

    def __init__(self, obj, tracker):
        self.tracked = obj
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
            self._tracker.get_field_tracker(name).get += 1
            return value

    def __setitem__(self, key, value):
        dict.__setitem__(self.tracked, key, value)

    def __delitem__(self, key):
        dict.__delitem__(self.tracked, key)

    def __iter__(self):
        return iter(self.tracked)


@functools.total_ordering
class TrackedSequence(TrackedObject, collections.abc.Sequence):
    __slots__ = ()

    def __getitem__(self, index):
        try:
            value = self.tracked.__getitem__(index)
        except IndexError:
            raise
        else:
            if type(index) is int:
                self._tracker.get_field_tracker(str(index)).get += 1
            else:
                for i in range(
                    index.start if index.start is not None else 0,
                    index.stop if index.stop is not None else len(self.tracked),
                    index.step if index.step else 1,
                ):
                    self._tracker.get_field_tracker(str(i)).get += 1
            return value

    def __lt__(self, other):
        return self.tracked < other

    def __eq__(self, other):
        return self.tracked == other

    def __hash__(self):
        return hash(self.tracked)


class TrackedResultCache(TrackedObject, collections.abc.Sequence):
    __slots__ = ()

    def __init__(self, obj, tracker):
        super().__init__(obj, tracker)
        weakref_finalize(self, self._tracker.result_cache_collected)

    def __getitem__(self, index):
        return self.tracked.__getitem__(index)

    def __len__(self):
        self._tracker["len_calls"] = self._tracker.get("len_calls", 0) + 1
        return len(self.tracked)

    def __contains__(self, value):
        self._tracker["contains_calls"] = self._tracker.get("contains_calls", 0) + 1
        return value in self.tracked

    def __bool__(self):
        self._tracker["exists_calls"] = self._tracker.get("exists_calls", 0) + 1
        return bool(self.tracked)


@functools.total_ordering
class FieldTracker(HashableMixin):
    __slots__ = ("get", "set")

    def __init__(self):
        self.get = self.set = 0

    __hash__ = HashableMixin.__hash__

    def hash_value(self):
        return hash((self.get, self.set))

    lazy_slots = (hash_value,)

    def __eq__(self, other):
        if type(other) is FieldTracker:
            return self.get == other.get and self.set == other.set
        return NotImplemented

    def __lt__(self, other):
        if type(other) is FieldTracker:
            return (self.get, self.set) < (other.get, other.set)
        elif not other:
            return False
        return NotImplemented


class InstanceTracker(dict):
    __slots__ = ()

    def __missing__(self, field):
        return

    def __getitem__(self, field, dict_get_item=dict.__getitem__):
        if not (field_tracker := dict_get_item(self, field)):
            self[field] = field_tracker = FieldTracker()
        return field_tracker

    get_field_tracker = __getitem__

    def __getstate__(self):
        return {"values": dict(self)}

    def __setstate__(self, state):
        self.update(state["values"])


new_instance_tracker = InstanceTracker.fromkeys


class ModelInstanceTracker(InstanceTracker, metaclass=LazySlots):
    __slots__ = ("queryset", "object")

    def related(self):
        return defaultdict(list)

    lazy_slots = (related,)

    def add_related_instance(self, instance, field, related_model):
        self.related[(field, related_model)].append(instance)

    def __getstate__(self):
        state = super().__getstate__()
        state.update(object=self.object(), queryset=self.queryset)
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        self.queryset = state["queryset"]
        if obj := state["object"]:
            self.object = weak_reference(obj)


new_model_instance_tracker = ModelInstanceTracker.fromkeys


class RequestTracker:
    __slots__ = (
        "request_info",
        "started_at",
        "finished",
        "queries",
        "num_queries",
        "num_queries_saved",
    )

    def __init__(self, request):
        self.request_info = {
            "path": request.path,
            "method": request.method,
            "content_type": request.content_type,
            "query_string": request.META.get("QUERY_STRING", ""),
        }
        self.started_at = now()
        self.finished = False
        self.queries = HashableCounter()
        self.num_queries = self.num_queries_saved = 0
        Collector.add_request(self)
        weakref_finalize(request, self.request_finished)

    def add_query(self, query_id):
        self.queries[query_id] += 1
        self.num_queries_saved += 1
        if self.ready:
            Collector.request_ready(self)

    def request_finished(self):
        self.finished = True
        if self.ready:
            Collector.request_ready(self)

    @property
    def ready(self):
        return self.finished and self.num_queries == self.num_queries_saved

    @staticmethod
    def save_trackers(trackers):
        get_or_create_request = RequestPromise.get_or_create
        get_or_create_query_group = QueryGroupPromise.get_or_create

        trackings = tuple(
            Tracking(
                started_at=tracker.started_at,
                request_id=get_or_create_request(**tracker.request_info),
                query_group_id=get_or_create_query_group(queries=tracker.queries),
            )
            for tracker in trackers
        )
        RequestPromise.resolve()
        QueryGroupPromise.resolve()
        return len(Tracking.objects.bulk_create(trackings))


class DummyRequestTracker:
    queries = Counter()

    @classmethod
    def add_query(cls, query_id):
        cls.queries[query_id] += 1

    @cached_attribute
    def query_group_id(cls):
        started_at = now()
        pk = hash(uuid.uuid1().int)

        with transaction.atomic(using=TRACKINGS_DB):
            request_id = RequestPromise.get_or_create(
                path="",
                method="",
                content_type="",
                query_string="",
            )
            RequestPromise.resolve()
            QueryGroup.objects.create(cache_key=pk)
            Tracking.objects.create(
                started_at=started_at, query_group_id=pk, request_id=request_id
            )

        return pk

    @classmethod
    def save_queries(cls):
        if not (queries := cls.queries):
            return

        queries = set(queries)
        pop_num_occurrences = cls.queries.pop
        query_group_id = cls.query_group_id

        saved = QuerySetTracking.objects.filter(
            query_group_id=query_group_id, query_id__in=queries
        )
        for obj in saved:
            obj.num_occurrences += pop_num_occurrences(obj.query_id)
            queries.remove(obj.query_id)
        if saved:
            QuerySetTracking.objects.bulk_update(saved, fields=["num_occurrences"])

        if queries:
            QueryPromise.resolve()
            QuerySetTracking.objects.bulk_create(
                QuerySetTracking(
                    query_id=query_id,
                    query_group_id=query_group_id,
                    num_occurrences=pop_num_occurrences(query_id),
                )
                for query_id in queries
            )


class QuerySetTracker(dict):
    constructors = {
        "related_querysets": list,
        "deferred_fields": lambda: defaultdict(set),
        "instance_trackers": lambda: defaultdict(list),
    }

    __slots__ = (
        "duration",
        "num_ready",
        "request_tracker",
        "related_queryset",
        "_iter_done",
        "_result_cache_collected",
        "constructed",
        *constructors,
    )

    def __getattr__(self, name):
        if constructor := self.constructors.get(name):
            value = constructor()
            setattr(self, name, value)
            self.constructed.add(name)
            return value
        raise AttributeError

    def __init__(
        self,
        queryset,
        query_type,
        iterable_class=None,
        track_attributes_accessed=False,
    ):
        super().__init__(
            sql="",
            num_instances=0,
            model=queryset.model,
            query_type=query_type,
            traceback=get_traceback(),
        )

        self.num_ready = 0
        self.constructed = set()
        self.related_queryset = None
        self._iter_done = self._result_cache_collected = False

        if iterable_class:
            self["iterable_class"] = iterable_class

        if track_attributes_accessed:
            self["attributes_accessed"] = HashableCounter()

        if (request := get_request()) is not DUMMY_REQUEST:
            self.request_tracker = request._tracker
            self.request_tracker.num_queries += 1
        else:
            self.request_tracker = DummyRequestTracker

        if (instance := queryset._hints.get("instance")) and (
            instance_tracker := getattr(instance, "_tracker", None)
        ):
            instance_tracker.queryset.add_related_queryset(self)
            if field := queryset._hints.get("field"):
                self["field"] = type(instance), field

        queryset._tracker = self

    def add_related_queryset(self, qs_tracker):
        self.related_querysets.append(qs_tracker)
        qs_tracker.related_queryset = self
        qs_tracker["depth"] = self.get("depth", 0) + 1

    def add_deferred_field(self, field, instance):
        self.deferred_fields[field].add(instance)

    def track_instance(self, instance, model, field="", *, tracker=None):
        self["num_instances"] += 1
        if tracker:
            self.instance_trackers[(field, model)].append(tracker)
            weakref_finalize(instance, self.instance_tracker_ready)
        else:
            self.num_ready += 1
        return instance

    def track_model_instance(self, instance, model, field=""):
        tracker = instance._tracker
        tracker.object = weak_reference(instance)
        tracker.queryset = self
        self.track_instance(instance, model, field, tracker=tracker)

        if related := getattr(tracker, "related", None):
            track_related_instance = self.track_model_instance
            for (
                related_field,
                related_model,
            ), related_instances in related.items():
                field_label = (
                    related_field if not field else f"{field}__{related_field}"
                )
                for related_instance in related_instances:
                    track_related_instance(related_instance, related_model, field_label)

            del tracker.related

        return instance

    def track_dict(self, d, model):
        tracker = new_instance_tracker(d)
        return self.track_instance(TrackedDict(d, tracker), model, tracker=tracker)

    def track_sequence(self, seq, model):
        tracker = new_instance_tracker(map(str, range(len(seq))))
        return self.track_instance(
            TrackedSequence(seq, tracker), model, tracker=tracker
        )

    @property
    def ready(self):
        return (
            self.num_ready == self["num_instances"]
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
        self.duration = duration
        self._iter_done = True

        if not (related_qs := self.related_queryset):
            Collector.add_tracker(self)
        elif self["num_instances"] == 1 and "deferred_fields" in related_qs.constructed:
            deferred_fields = related_qs.deferred_fields
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
                    self["field"] = queryset.model, loaded_fields[0]
                    deferred_fields[loaded_fields[0]].remove(instance)

    def save(self):
        if "instance_trackers" in self.constructed:
            self["instance_trackings"] = frozenset(
                (
                    model,
                    select_related_field,
                    HashableCounter(
                        chain.from_iterable(tracker.items() for tracker in trackers)
                    ),
                )
                for (
                    select_related_field,
                    model,
                ), trackers in self.instance_trackers.items()
            )

        query_id = QueryPromise.get_or_create(**self)
        QueryPromise.update_duration(query_id, self.duration)

        if "related_querysets" in self.constructed:
            for related_tracker in self.related_querysets:
                related_tracker["related_queryset_id"] = query_id
                Collector.add_tracker(related_tracker)
                del related_tracker.related_queryset

        self.request_tracker.add_query(query_id)

    @staticmethod
    def save_trackers(trackers):
        deque((tracker.save() for tracker in trackers), maxlen=0)
        QueryPromise.resolve()
        return len(trackers)

    def __hash__(self):
        return id(self)
