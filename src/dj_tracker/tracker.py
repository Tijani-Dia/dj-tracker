import atexit
import threading
from functools import lru_cache, partial, wraps
from time import perf_counter_ns

from django.db import connection
from django.db.models import query

from dj_tracker.collector import Collector
from dj_tracker.constants import (
    DUMMY_REQUEST,
    EXTRA_DESCRIPTORS,
    IGNORED_PATHS,
    STOPPING,
    TRACK_ATTRIBUTES_ACCESSED,
    TRACKED_MODELS,
)
from dj_tracker.context import get_request, set_request
from dj_tracker.datastructures import (
    QuerySetTracker,
    TrackedResultCache,
    new_model_instance_tracker,
)
from dj_tracker.field_descriptors import DESCRIPTORS_MAP
from dj_tracker.logging import logger
from dj_tracker.models import QueryType

_started = False
_worker_thread = None
_lock = threading.Lock()


@lru_cache
def model_is_tracked(model):
    return model in TRACKED_MODELS


@lru_cache
def ignore_path(path):
    return any(component in path for component in IGNORED_PATHS)


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


def patch_queryset_method(method, query_type):
    @wraps(method)
    def wrapper(queryset):
        if (
            queryset._result_cache is None
            and model_is_tracked(queryset.model)
            and not ignore_path(get_request().path)
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
    def wrapper(from_obj, obj):
        local_setter(from_obj, obj)
        if obj is not None:
            from_obj._tracker.add_related_instance(obj, field, related_model)

    return wrapper


def track_instances(Iterable, track_attributes_accessed, instance_tracker):
    assert not hasattr(Iterable, "__patched")
    iterate = Iterable.__iter__
    query_type = QueryType.SELECT

    @wraps(iterate)
    def __iter__(self):
        qs = self.queryset
        model = qs.model

        if not model_is_tracked(model) or ignore_path(get_request().path):
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
    for Iterable, track_attributes_accessed, instance_tracker in (
        (query.ModelIterable, TRACK_ATTRIBUTES_ACCESSED, "track_model_instance"),
        (query.ValuesIterable, False, "track_dict"),
        (query.ValuesListIterable, False, "track_sequence"),
        (query.FlatValuesListIterable, False, "track_instance"),
    ):
        track_instances(Iterable, track_attributes_accessed, instance_tracker)
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


def execute_wrapper(execute, sql, params, many, context, *, qs_tracker):
    qs_tracker["sql"] = sql % params
    return execute(sql, params, many, context)


def patch_requests():
    from django.core.handlers import asgi, wsgi
    from django.core.signals import request_finished

    send_request_finished = request_finished.send

    def init_request_wrapper(init_request):
        @wraps(init_request)
        def __init__(request, *args):
            init_request(request, *args)
            set_request(request)

        return __init__

    @wraps(send_request_finished)
    def req_finished(sender, **named):
        result = send_request_finished(sender, **named)
        if tracker := getattr(get_request(), "_tracker", None):
            tracker.request_finished()

        set_request(DUMMY_REQUEST)
        return result

    wsgi.WSGIRequest.__init__ = init_request_wrapper(wsgi.WSGIRequest.__init__)
    asgi.ASGIRequest.__init__ = init_request_wrapper(asgi.ASGIRequest.__init__)
    request_finished.send = req_finished


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
    with _lock:
        global _started, _worker_thread
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

        _worker_thread = threading.Thread(target=Collector.run, daemon=True)
        _worker_thread.start()
        _started = True


@atexit.register
def stop():
    global _worker_thread
    if _worker_thread and not STOPPING.is_set():
        STOPPING.set()
        logger.info("Saving latest trackings...")
        _worker_thread.join()
        _worker_thread = None
