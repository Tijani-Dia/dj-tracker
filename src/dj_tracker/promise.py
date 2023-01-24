from typing import Dict, FrozenSet, Hashable, Optional, Tuple

from django.apps import apps
from django.db.models.base import ModelBase
from django.db.models.query import BaseIterable

from dj_tracker.cache_utils import LRUCache, cached_attribute
from dj_tracker.hash_utils import HashableCounter, HashableList, hash_string
from dj_tracker.models import (
    InstanceFieldTracking,
    QuerySetTracking,
    QueryType,
    StackEntry,
)


class Promise:
    # Promise class(es) this one depends on,
    # typically via foreign keys on the model it represents.
    deps = ()

    __slots__ = ("cache_key", "creation_kwargs")

    @classmethod
    def __init_subclass__(cls, *, cache_size=512):
        cls.model = apps.get_model(
            "dj_tracker", cls.__name__[:-7]  # removesuffix("Promise")
        )
        cls.to_resolve = to_resolve = {}
        cls.resolve_promise = to_resolve.pop

        get_cache_key = cls.get_cache_key
        get_in_memory_key = cls.get_in_memory_key
        set_creation_kwargs = getattr(cls, "set_creation_kwargs", None)

        cache = LRUCache(maxsize=cache_size)
        cache_get = cache.get
        cache_set = cache.set

        def get_or_create(**kwargs):
            in_memory_key = get_in_memory_key(**kwargs)
            if not (cache_key := cache_get(in_memory_key)):
                if set_creation_kwargs:
                    set_creation_kwargs(kwargs)
                if (cache_key := get_cache_key(**kwargs)) not in to_resolve:
                    to_resolve[cache_key] = cls(cache_key, kwargs)

                cache_set(in_memory_key, cache_key)

            return cache_key

        cls.get_or_create = get_or_create

    @staticmethod
    def get_in_memory_key(**kwargs) -> Hashable:
        raise NotImplementedError

    @staticmethod
    def get_cache_key(**kwargs) -> int:
        """
        Computes the cache key for the given keyword arguments.
        The implementation of this method must be deterministic;
        given a particular input, it must always produce the same output.
        """
        raise NotImplementedError

    def __init__(self, cache_key: int, creation_kwargs: Dict):
        """
        `cache_key` is used to find existing model instances.
        When no instance matches the given key, a new one is created
        using the `creation_kwargs`.
        """
        self.cache_key = cache_key
        self.creation_kwargs = creation_kwargs

    @classmethod
    def obj_created(cls, cache_key: int):
        """
        Hook run when an object with the given `cache_key` is created
        """
        # Remove and return the corresponding promise from `to_resolve`.
        return cls.resolve_promise(cache_key)

    @cached_attribute
    def queryset(cls):
        return cls.model.objects.only("cache_key").values_list("cache_key", flat=True)

    @classmethod
    def resolve_existing(cls, to_resolve):
        """
        Finds all existing objects with primary keys matching the ones in `to_resolve`
        and resolves the corresponding promises.
        """
        resolve_promise = cls.resolve_promise
        for cache_key in cls.queryset.filter(cache_key__in=to_resolve).iterator():
            del to_resolve[cache_key]
            resolve_promise(cache_key)

    @classmethod
    def resolve_new(cls, to_resolve):
        """
        Creates new model instances for the promises in `to_resolve`.
        """
        Model = cls.model
        obj_created = cls.obj_created
        Model.objects.bulk_create(
            Model(cache_key=cache_key, **promise.creation_kwargs)
            for cache_key, promise in to_resolve.items()
        )
        for cache_key in to_resolve:
            obj_created(cache_key)

    @classmethod
    def resolve(cls):
        """
        Resolves existing and new model instances as requested in `cls.get_or_create`.
        Ideally, this should be called when a lot of promises need to be resolved,
        to benefit more from doing things in bulk.
        """
        if not (to_resolve := cls.to_resolve):
            return

        # Copy the current set of promises as other promises may be
        # added to the `to_resolve` dict  while this method is running.
        # Also, we need to make the copy *before* resolving dependencies,
        # otherwise we may copy promises for which some deps weren't resolved.
        to_resolve = to_resolve.copy()
        for dep in cls.deps:
            dep.resolve()

        cls.resolve_existing(to_resolve)
        if to_resolve:
            cls.resolve_new(to_resolve)


class ModelPromise(Promise):
    __slots__ = ()

    @staticmethod
    def get_in_memory_key(*, model: ModelBase) -> ModelBase:
        return model

    @staticmethod
    def set_creation_kwargs(kwargs):
        kwargs["label"] = kwargs.pop("model")._meta.label

    @staticmethod
    def get_cache_key(*, label: str) -> int:
        return hash_string(label)


class FieldPromise(Promise):
    deps = (ModelPromise,)

    __slots__ = ()

    @staticmethod
    def get_in_memory_key(*, model: ModelBase, name: str) -> str:
        return f"{model.__name__}{name}"

    @staticmethod
    def set_creation_kwargs(kwargs):
        kwargs["model_id"] = ModelPromise.get_or_create(model=kwargs.pop("model"))

    @staticmethod
    def get_cache_key(*, model_id: int, name: str) -> int:
        return hash((model_id, hash_string(name)))


class SQLPromise(Promise):
    __slots__ = ()

    @staticmethod
    def get_in_memory_key(*, sql: str) -> str:
        return sql

    @staticmethod
    def get_cache_key(*, sql: str) -> int:
        return hash_string(sql)


class URLPathPromise(Promise):
    __slots__ = ()

    @staticmethod
    def get_in_memory_key(*, path: str) -> str:
        return path

    @staticmethod
    def get_cache_key(*, path: str) -> int:
        return hash_string(path)


class RequestPromise(Promise):
    deps = (URLPathPromise,)

    __slots__ = ()

    @staticmethod
    def get_in_memory_key(
        *, path: str, method: str, content_type: str, query_string: str
    ) -> str:
        return f"{path}{method}{content_type}{query_string}"

    @staticmethod
    def set_creation_kwargs(kwargs):
        kwargs["path_id"] = URLPathPromise.get_or_create(path=kwargs.pop("path"))

    @staticmethod
    def get_cache_key(
        *, path_id: int, method: str, content_type: str, query_string: str
    ) -> int:
        return hash(
            (
                path_id,
                hash_string(method),
                hash_string(content_type),
                hash_string(query_string),
            )
        )


class SourceFilePromise(Promise):
    __slots__ = ()

    @staticmethod
    def get_in_memory_key(*, name: str) -> str:
        return name

    @staticmethod
    def get_cache_key(*, name: str) -> int:
        return hash_string(name)


class SourceCodePromise(Promise):
    deps = (SourceFilePromise,)

    __slots__ = ()

    @staticmethod
    def get_in_memory_key(*, entry) -> int:
        return entry.hash_value

    @staticmethod
    def get_cache_key(*, entry) -> int:
        return entry.cache_key

    def __init__(self, cache_key, creation_kwargs):
        entry = creation_kwargs["entry"]
        super().__init__(
            cache_key,
            {
                "filename_id": entry.filename_id,
                "lineno": entry.lineno,
                "func": entry.func,
                "code": entry.code,
            },
        )


class TracebackPromise(Promise):
    deps = (SourceCodePromise,)

    stack_entries = []

    __slots__ = "stack"

    @staticmethod
    def get_in_memory_key(*, stack: HashableList, template_info) -> int:
        return (
            stack.hash_value
            if not template_info
            else hash((stack.hash_value, template_info.hash_value))
        )

    @staticmethod
    def set_creation_kwargs(kwargs):
        get_or_create_source_code = SourceCodePromise.get_or_create
        kwargs["stack"] = tuple(
            get_or_create_source_code(entry=entry) for entry in kwargs["stack"]
        )
        if template_info := kwargs.pop("template_info"):
            kwargs["template_info_id"] = get_or_create_source_code(entry=template_info)

    @staticmethod
    def get_cache_key(*, stack: Tuple, template_info_id: Optional[int] = None):
        return hash((stack, template_info_id)) if template_info_id else hash(stack)

    def __init__(self, cache_key, creation_kwargs):
        self.stack = creation_kwargs.pop("stack")
        super().__init__(cache_key, creation_kwargs)

    @classmethod
    def obj_created(cls, cache_key: int) -> "TracebackPromise":
        """
        Adds new stack entries for save when a `Traceback` instance is created.
        """
        promise = super().obj_created(cache_key)
        cls.stack_entries.extend(
            StackEntry(traceback_id=cache_key, source_id=source_id, index=index)
            for index, source_id in enumerate(reversed(promise.stack))
        )
        return promise

    @classmethod
    def resolve(cls):
        super().resolve()
        if stack_entries := cls.stack_entries:
            StackEntry.objects.bulk_create(stack_entries)
            stack_entries.clear()


class FieldTrackingPromise(Promise):
    deps = (FieldPromise,)

    __slots__ = ()

    @staticmethod
    def get_in_memory_key(*, model: ModelBase, field: str, field_tracker) -> int:
        return hash((model, field, field_tracker))

    @staticmethod
    def set_creation_kwargs(kwargs):
        kwargs["field_id"] = FieldPromise.get_or_create(
            model=kwargs.pop("model"), name=kwargs.pop("field")
        )

    @staticmethod
    def get_cache_key(*, field_id: int, field_tracker):
        return field_id if not field_tracker else hash((field_id, field_tracker))

    def __init__(self, cache_key, creation_kwargs):
        if field_tracker := creation_kwargs.pop("field_tracker"):
            creation_kwargs.update(
                get_count=field_tracker.get, set_count=field_tracker.set
            )
        super().__init__(cache_key, creation_kwargs)


class InstanceTrackingPromise(Promise):
    deps = (FieldTrackingPromise,)

    trackings = []

    __slots__ = "field_trackings"

    @staticmethod
    def get_in_memory_key(
        *,
        model: ModelBase,
        select_related_field: str,
        field_trackings: HashableCounter,
    ):
        return hash((model, select_related_field, field_trackings))

    @staticmethod
    def set_creation_kwargs(kwargs):
        model = kwargs.pop("model")
        get_field_tracking_id = FieldTrackingPromise.get_or_create

        kwargs["field_trackings"] = frozenset(
            (
                get_field_tracking_id(
                    model=model, field=field, field_tracker=field_tracker
                ),
                num_occurrences,
            )
            for (field, field_tracker), num_occurrences in kwargs[
                "field_trackings"
            ].items()
        )

    @staticmethod
    def get_cache_key(
        field_trackings: FrozenSet[Tuple[int, int]], select_related_field: str
    ) -> int:
        return (
            hash(field_trackings)
            if not select_related_field
            else hash((field_trackings, hash_string(select_related_field)))
        )

    def __init__(self, cache_key, creation_kwargs):
        self.field_trackings = creation_kwargs.pop("field_trackings")
        super().__init__(cache_key, creation_kwargs)

    @classmethod
    def obj_created(cls, cache_key: int) -> "InstanceTrackingPromise":
        """
        Adds new instance field trackings for save when
        an `InstanceTracking` instance is created.
        """
        promise = super().obj_created(cache_key)

        cls.trackings.extend(
            InstanceFieldTracking(
                instance_tracking_id=cache_key,
                field_tracking_id=field_tracking_id,
                num_occurrences=num_occurrences,
            )
            for field_tracking_id, num_occurrences in promise.field_trackings
        )
        return promise

    @classmethod
    def resolve(cls):
        super().resolve()
        if trackings := cls.trackings:
            InstanceFieldTracking.objects.bulk_create(trackings)
            trackings.clear()


class QueryPromise(Promise):
    deps = (TracebackPromise, SQLPromise, ModelPromise, InstanceTrackingPromise)

    trackings = []
    durations = {}

    __slots__ = "instance_trackings"

    @staticmethod
    def get_in_memory_key(
        *,
        sql: str,
        model: ModelBase,
        num_instances: int,
        query_type: QueryType,
        traceback: Tuple,
        depth: Optional[int] = None,
        cache_hits: Optional[int] = None,
        len_calls: Optional[int] = None,
        exists_calls: Optional[int] = None,
        contains_calls: Optional[int] = None,
        field: Optional[Tuple[ModelBase, str]] = None,
        iterable_class: Optional[BaseIterable] = None,
        instance_trackings: Optional[FrozenSet] = None,
        related_queryset_id: Optional[int] = None,
        attributes_accessed: Optional[HashableCounter] = None,
    ) -> int:
        return hash(
            (
                depth,
                query_type,
                cache_hits,
                num_instances,
                iterable_class,
                instance_trackings,
                attributes_accessed,
                len_calls,
                exists_calls,
                contains_calls,
                sql,
                field,
                model,
                traceback,
                related_queryset_id,
            )
        )

    @staticmethod
    def set_creation_kwargs(kwargs):
        stack, template_info = kwargs.pop("traceback")
        kwargs.update(
            sql_id=SQLPromise.get_or_create(sql=kwargs.pop("sql")),
            model_id=ModelPromise.get_or_create(model=kwargs.pop("model")),
            traceback_id=TracebackPromise.get_or_create(
                stack=stack, template_info=template_info
            ),
        )
        if related_field := kwargs.pop("field", None):
            kwargs["field_id"] = FieldPromise.get_or_create(
                model=related_field[0], name=related_field[1]
            )
        if instance_trackings := kwargs.get("instance_trackings"):
            get_instance_tracking_id = InstanceTrackingPromise.get_or_create
            kwargs["instance_trackings"] = frozenset(
                get_instance_tracking_id(
                    model=model,
                    field_trackings=field_trackings,
                    select_related_field=select_related_field,
                )
                for model, select_related_field, field_trackings in instance_trackings
            )
        if iterable_class := kwargs.get("iterable_class"):
            kwargs["iterable_class"] = iterable_class.__name__

    @staticmethod
    def get_cache_key(
        *,
        query_type: str,
        num_instances: int,
        sql_id: int,
        model_id: int,
        traceback_id: int,
        depth: Optional[int] = None,
        cache_hits: Optional[int] = None,
        field_id: Optional[int] = None,
        len_calls: Optional[int] = None,
        exists_calls: Optional[int] = None,
        contains_calls: Optional[int] = None,
        iterable_class: Optional[str] = None,
        instance_trackings: Optional[FrozenSet] = None,
        related_queryset_id: Optional[int] = None,
        attributes_accessed: Optional[HashableCounter] = None,
    ) -> int:
        return hash(
            (
                sql_id,
                model_id,
                traceback_id,
                num_instances,
                hash_string(str(query_type)),
                depth if depth else 0,
                field_id if field_id else 0,
                cache_hits if cache_hits else 0,
                len_calls if len_calls else 0,
                exists_calls if exists_calls else 0,
                contains_calls if contains_calls else 0,
                instance_trackings if instance_trackings else 0,
                hash_string(iterable_class) if iterable_class else 0,
                hash(
                    frozenset(
                        (hash_string(attr), count)
                        for attr, count in attributes_accessed.items()
                    )
                )
                if attributes_accessed
                else 0,
                related_queryset_id if related_queryset_id else 0,
            )
        )

    def __init__(self, cache_key, creation_kwargs):
        if instance_trackings := creation_kwargs.pop("instance_trackings", None):
            self.instance_trackings = instance_trackings
        super().__init__(cache_key, creation_kwargs)

    @classmethod
    def obj_created(cls, cache_key: int) -> "QueryPromise":
        promise = super().obj_created(cache_key)
        if instance_trackings := getattr(promise, "instance_trackings", None):
            InstanceTracking = cls.model.instance_trackings.through
            cls.trackings.extend(
                InstanceTracking(
                    query_id=cache_key,
                    instancetracking_id=instance_tracking_id,
                )
                for instance_tracking_id in instance_trackings
            )
        return promise

    @classmethod
    def resolve(cls):
        super().resolve()
        if trackings := cls.trackings:
            cls.model.instance_trackings.through.objects.bulk_create(trackings)
            trackings.clear()

        if cls.durations:
            cls.update_durations()

    @classmethod
    def update_duration(cls, cache_key, duration):
        if not (prev_duration := cls.durations.get(cache_key)):
            cls.durations[cache_key] = duration
        else:
            cls.durations[cache_key] = prev_duration + duration / 2

    @classmethod
    def update_durations(cls):
        Manager = cls.model.objects
        to_update = Manager.filter(pk__in=tuple(cls.durations)).only(
            "cache_key", "average_duration"
        )
        pop_average_duration = cls.durations.pop
        for query in to_update:
            avg_duration = pop_average_duration(query.cache_key)
            if prev_duration := query.average_duration:
                query.average_duration = prev_duration + avg_duration / 2
            else:
                query.average_duration = avg_duration

        Manager.bulk_update(to_update, fields=["average_duration"])


class QueryGroupPromise(Promise, cache_size=128):
    trackings = []

    __slots__ = "queries"

    @staticmethod
    def get_in_memory_key(*, queries) -> int:
        return queries.hash_value

    get_cache_key = get_in_memory_key

    def __init__(self, cache_key, creation_kwargs):
        self.queries = creation_kwargs.pop("queries")
        super().__init__(cache_key, creation_kwargs)

    @classmethod
    def obj_created(cls, cache_key: int) -> "QueryGroupPromise":
        """
        Adds new queryset trackings for save when a `QueryGroup` instance is created.
        """
        promise = super().obj_created(cache_key)
        cls.trackings.extend(
            QuerySetTracking(
                query_id=query_id,
                query_group_id=cache_key,
                num_occurrences=num_occurrences,
            )
            for query_id, num_occurrences in promise.queries.items()
        )
        return promise

    @classmethod
    def resolve(cls):
        super().resolve()
        if trackings := cls.trackings:
            QuerySetTracking.objects.bulk_create(trackings)
            trackings.clear()
