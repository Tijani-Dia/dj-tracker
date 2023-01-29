import threading
from functools import lru_cache, partial, wraps
from time import perf_counter_ns

from django.core import signals
from django.core.handlers import asgi, wsgi
from django.db import connection
from django.db.models import query
from django.utils.functional import cached_property

from dj_tracker.collector import Collector
from dj_tracker.constants import (
    DUMMY_REQUEST,
    EXTRA_DESCRIPTORS,
    IGNORED_PATHS,
    TRACK_ATTRIBUTES_ACCESSED,
    TRACKED_MODELS,
)
from dj_tracker.context import get_request, set_request
from dj_tracker.datastructures import (
    QuerySetTracker,
    RequestTracker,
    TrackedResultCache,
    new_model_instance_tracker,
)
from dj_tracker.field_descriptors import DESCRIPTORS_MAP
from dj_tracker.models import QueryType

_started = False
_lock = threading.Lock()

stop = Collector.stop


class FromDBDescriptor:
    __slots__ = ("model", "__func__")

    def __init__(self, model):
        self.model = model
        # model.from_db is a classmethod, so we store the actual function.
        # This will keep inheritance rules.
        self.__func__ = model.from_db.__func__

    def __call__(self, db, field_names, values):
        instance = self.__func__(self.model, db, field_names, values)
        instance._tracker = new_model_instance_tracker(field_names)
        return instance


class ResultCacheDescriptor:
    def __get__(self, queryset, cls):
        if queryset is None:
            return self

        if (result_cache := queryset.__dict__["_result_cache"]) is not None and (
            qs_tracker := getattr(queryset, "_tracker", None)
        ):
            qs_tracker["cache_hits"] += 1

        return result_cache

    def __set__(self, queryset, value):
        if value is not None and (qs_tracker := getattr(queryset, "_tracker", None)):
            qs_tracker["cache_hits"] = 0
            value = TrackedResultCache(value, qs_tracker)

        queryset.__dict__["_result_cache"] = value


def execute_wrapper(execute, sql, params, many, context, *, qs_tracker):
    qs_tracker["sql"] = sql
    return execute(sql, params, many, context)


def patch_queryset_method(method, query_type):
    @wraps(method)
    def wrapper(queryset):
        if (
            queryset._result_cache is None
            and queryset.model in TRACKED_MODELS
            and not get_request()._ignore_path
        ):
            qs_tracker = QuerySetTracker(queryset, query_type)

            with connection.execute_wrapper(
                partial(execute_wrapper, qs_tracker=qs_tracker)
            ):
                started_at = perf_counter_ns()
                result = method(queryset)
                duration = perf_counter_ns() - started_at

            qs_tracker.iter_done(queryset, duration)
            qs_tracker.result_cache_collected()
        else:
            result = method(queryset)

        return result

    return wrapper


def track_instances(Iterable, track_attributes_accessed, instance_tracker):
    assert not hasattr(Iterable, "__patched")
    iterate = Iterable.__iter__
    query_type = QueryType.SELECT

    @wraps(iterate)
    def __iter__(self):
        qs = self.queryset
        model = qs.model

        if model not in TRACKED_MODELS or get_request()._ignore_path:
            yield from iterate(self)
            return

        qs_tracker = QuerySetTracker(
            qs, query_type, self.__class__, track_attributes_accessed
        )
        track_instance = getattr(qs_tracker, instance_tracker)

        with connection.execute_wrapper(
            partial(execute_wrapper, qs_tracker=qs_tracker)
        ):
            started_at = perf_counter_ns()
            for obj in iterate(self):
                yield track_instance(obj, model)
            duration = perf_counter_ns() - started_at

        qs_tracker.iter_done(qs, duration)

    Iterable.__iter__ = __iter__


def patch_iterables():
    for Iterable, track_attributes_accessed, instance_tracker in (
        (query.ModelIterable, TRACK_ATTRIBUTES_ACCESSED, "track_model_instance"),
        (query.ValuesIterable, False, "track_dict"),
        (query.ValuesListIterable, False, "track_sequence"),
        (query.FlatValuesListIterable, False, "track_instance"),
    ):
        track_instances(Iterable, track_attributes_accessed, instance_tracker)
        Iterable.__patched = True


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


def patch_queryset():
    QuerySet = query.QuerySet
    assert not hasattr(QuerySet, "__patched")

    QuerySet.exists = patch_queryset_method(QuerySet.exists, QueryType.EXISTS)
    QuerySet.count = patch_queryset_method(QuerySet.count, QueryType.COUNT)
    QuerySet._iterator = patch_iterator(QuerySet._iterator)
    QuerySet._result_cache = ResultCacheDescriptor()
    QuerySet.__contains__ = contains_patch
    QuerySet.__patched = True


def wrap_local_setter(local_setter, field, related_model):
    def wrapper(from_obj, obj):
        local_setter(from_obj, obj)
        if obj is not None:
            from_obj._tracker.add_related_instance(obj, field, related_model)

    return wrapper


def patch_rel_populator():
    init = query.RelatedPopulator.__init__

    @wraps(init)
    def wrapper(self, klass_info, *args):
        if (model := klass_info["model"]) in TRACKED_MODELS:
            klass_info["local_setter"] = wrap_local_setter(
                klass_info["local_setter"], klass_info["field"].name, model
            )

        init(self, klass_info, *args)

    query.RelatedPopulator.__init__ = wrapper


def patch_requests():
    @lru_cache
    def ignore_path(path):
        return any(component in path for component in IGNORED_PATHS)

    def patch_init(init):
        @wraps(init)
        def wrapper(request, *args):
            init(request, *args)
            request._ignore_path = ignore_path(request.path)
            set_request(request)

        return wrapper

    def patch_send(send):
        @wraps(send)
        def wrapper(sender, **named):
            try:
                return send(sender, **named)
            finally:
                set_request(DUMMY_REQUEST)

        return wrapper

    @cached_property
    def get_tracker(request):
        return RequestTracker(request)

    # Patch `__init__`.
    wsgi.WSGIRequest.__init__ = patch_init(wsgi.WSGIRequest.__init__)
    asgi.ASGIRequest.__init__ = patch_init(asgi.ASGIRequest.__init__)

    # Patch `request_finished` signal.
    signals.request_finished.send = patch_send(signals.request_finished.send)

    # Add cached_property `_tracker` to requests classes.
    wsgi.WSGIRequest._tracker = asgi.ASGIRequest._tracker = get_tracker
    get_tracker.__set_name__(wsgi.WSGIRequest, "_tracker")
    get_tracker.__set_name__(asgi.ASGIRequest, "_tracker")


def patch_getattr():
    get_attr = object.__getattribute__
    tracker_attr = "_tracker"

    @wraps(get_attr)
    def wrapper(instance, attr):
        value = get_attr(instance, attr)
        if attr != tracker_attr:
            try:
                instance_tracker = get_attr(instance, tracker_attr)
            except AttributeError:
                pass
            else:
                if (
                    qs_tracker := getattr(instance_tracker, "queryset", None)
                ) and attr not in instance_tracker:
                    qs_tracker["attributes_accessed"][attr] += 1

        return value

    return wrapper


def start():
    global _started

    with _lock:
        if _started:
            return

        patch_queryset()
        patch_iterables()
        patch_rel_populator()
        patch_requests()

        descriptors = {**DESCRIPTORS_MAP, **EXTRA_DESCRIPTORS}
        for model in TRACKED_MODELS:
            model.from_db = FromDBDescriptor(model)
            for attname, attr in model.__dict__.items():
                if Descriptor := descriptors.get(type(attr).__name__):
                    setattr(model, attname, Descriptor(attr, attname))

        if TRACK_ATTRIBUTES_ACCESSED:
            patched_get_attr = patch_getattr()
            for model in TRACKED_MODELS:
                model.__getattribute__ = patched_get_attr

        Collector.start()
        _started = True
