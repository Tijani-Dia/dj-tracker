import atexit
import threading
from functools import wraps
from time import perf_counter_ns

from django.db.models import DEFERRED, query

from dj_tracker.collector import Collector
from dj_tracker.constants import IGNORED_PATHS, STOPPING, TRACKED_MODELS
from dj_tracker.context import get_request
from dj_tracker.datastructures import (
    FieldTracker,
    InstanceTracker,
    QuerySetTracker,
    TrackedResultCache,
)
from dj_tracker.field_descriptors import DESCRIPTORS_MAP
from dj_tracker.models import QueryType

_started = False
_worker_thread = None
_lock = threading.Lock()


class FromDBDescriptor:
    def __init__(self, model):
        self.model = model
        # model.from_db is a classmethod, so we store the actual function.
        # This will keep inheritance rules.
        self.__func__ = model.from_db.__func__

    def __call__(self, db, field_names, values):
        new = self.__func__(self.model, db, field_names, values)
        new._tracker = InstanceTracker(
            zip(
                field_names,
                (FieldTracker() for value in values if value is not DEFERRED),
            )
        )
        return new


class ResultCacheDescriptor:
    def __get__(self, queryset, cls):
        if queryset is None:
            return self

        if (result_cache := queryset.__dict__["_result_cache"]) is not None and (
            qs_tracker := getattr(queryset, "_tracker", None)
        ):
            qs_tracker.cache_hits += 1

        return result_cache

    def __set__(self, queryset, value):
        if value is not None and (qs_tracker := getattr(queryset, "_tracker", None)):
            qs_tracker.cache_hits = 0
            value = TrackedResultCache(value, qs_tracker)

        queryset.__dict__["_result_cache"] = value


def patch_queryset_method(method, query_type):
    @wraps(method)
    def wrapper(queryset):
        cached_result = queryset._result_cache
        if tracking := cached_result is None and should_track_query(queryset.model):
            started_at = perf_counter_ns()

        result = method(queryset)

        if tracking:
            duration = perf_counter_ns() - started_at
            QuerySetTracker(
                queryset, query_type, result_cache_collected=True
            ).iter_done(queryset, duration)

        return result

    return wrapper


def patch_iterator(iterate):
    @wraps(iterate)
    def wrapper(queryset, *args):
        yield from iterate(queryset, *args)
        if qs_tracker := getattr(queryset, "_tracker", None):
            qs_tracker.result_cache_collected()

    return wrapper


def contains_patch(queryset, obj):
    queryset._fetch_all()
    return obj in queryset._result_cache


def wrap_local_setter(local_setter, field, related_model):
    @wraps(local_setter)
    def wrapper(from_obj, obj):
        local_setter(from_obj, obj)
        from_obj._tracker.add_related_instance(obj, field, related_model)

    return wrapper


def track_instances(Iterable, check_accessed_instances):
    assert not hasattr(Iterable, "__patched")
    iterate = Iterable.__iter__

    @wraps(iterate)
    def __iter__(self):
        iterator = iterate(self)
        qs = self.queryset
        model = qs.model

        if not should_track_query(model):
            yield from iterator
            return

        qs_tracker = QuerySetTracker(
            qs,
            QueryType.SELECT,
            check_accessed_instances,
            iterable_class=self.__class__.__name__,
        )
        track_instance = qs_tracker.track_instance
        started_at = perf_counter_ns()

        for obj in iterator:
            yield track_instance(obj, model)
            qs_tracker.num_instances += 1

        duration = perf_counter_ns() - started_at
        qs_tracker.iter_done(qs, duration)

    Iterable.__iter__ = __iter__


def patch_queryset():
    QuerySet = query.QuerySet
    assert not hasattr(QuerySet, "__patched")

    QuerySet.exists = patch_queryset_method(QuerySet.exists, QueryType.EXISTS)
    QuerySet.count = patch_queryset_method(QuerySet.count, QueryType.COUNT)
    QuerySet._iterator = patch_iterator(QuerySet._iterator)
    QuerySet._result_cache = ResultCacheDescriptor()
    QuerySet.__contains__ = contains_patch
    QuerySet.__patched = True


def patch_iterables():
    for Iterable, check_accessed_instances in (
        (query.ModelIterable, True),
        (query.ValuesIterable, False),
        (query.ValuesListIterable, False),
        (query.FlatValuesListIterable, False),
    ):
        track_instances(Iterable, check_accessed_instances)
        Iterable.__patched = True


def patch_rel_populator():
    init = query.RelatedPopulator.__init__

    @wraps(init)
    def wrapper(self, klass_info, *args):
        model = klass_info["model"]
        if model_is_tracked(model):
            klass_info["local_setter"] = wrap_local_setter(
                klass_info["local_setter"], klass_info["field"].name, model
            )

        init(self, klass_info, *args)

    query.RelatedPopulator.__init__ = wrapper


def patch_getattr():
    get_attr = object.__getattribute__

    @wraps(get_attr)
    def wrapper(obj, name):
        try:
            tracker = get_attr(obj, "_tracker").queryset
        except AttributeError:
            pass
        else:
            tracker._attributes_accessed[name] += 1

        return get_attr(obj, name)

    return wrapper


def start():
    with _lock:
        global _started, _worker_thread
        if _started:
            return

        patch_queryset()
        patch_iterables()
        patch_rel_populator()

        patched_get_attr = patch_getattr()
        for model in TRACKED_MODELS:
            model.from_db = FromDBDescriptor(model)
            model.__getattribute__ = patched_get_attr

            for attname, attr in model.__dict__.items():
                if (klass := type(attr)) in DESCRIPTORS_MAP:
                    Descriptor = DESCRIPTORS_MAP[klass]
                    setattr(model, attname, Descriptor(attr, attname))

        _worker_thread = threading.Thread(target=Collector.run, daemon=True)
        _worker_thread.start()
        _started = True


@atexit.register
def stop():
    global _worker_thread
    if _worker_thread:
        STOPPING.set()
        _worker_thread.join()
        _worker_thread = None


def model_is_tracked(model):
    return model in TRACKED_MODELS


def ignore_path(path):
    return any(component in path for component in IGNORED_PATHS)


def should_track_query(model):
    return model_is_tracked(model) and not ignore_path(get_request().path)
