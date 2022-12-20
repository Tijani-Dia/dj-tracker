from collections import Counter
from itertools import takewhile
from linecache import getline
from sys import _getframe
from typing import Dict, Optional, Tuple

from django.apps import apps
from django.db import models

from dj_tracker.utils import cached_attribute, delay, hash_string, ignore_frame


class Promisable(models.Model):
    """
    A Promisable is a model whose instances' primary keys (`cache_key`)
    are deduced from the data they hold.
    """

    cache_key = models.BigIntegerField(primary_key=True)

    class Meta:
        abstract = True


class Promise:
    # Model to attach to this promise class.
    model_string = None
    # Promise class(es) this one depends on,
    # typically via foreign keys on the model they represent.
    deps = ()

    __slots__ = ("cache_key", "creation_kwargs")

    @classmethod
    def __init_subclass__(cls):
        super().__init_subclass__()
        # Set of cache keys corresponding to resolved promises/model instances.
        cls.resolved = set()

        # Mapping of `cache_key: promise` representing the current
        # set of promises to resolve.
        cls.to_resolve = {}

    def __init__(self, cache_key: int, **creation_kwargs):
        """
        `cache_key` is used to find existing model instances.
        When no instance matches the given key, a new one is created
        using the `creation_kwargs`.
        """
        self.cache_key = cache_key
        self.creation_kwargs = creation_kwargs

    @staticmethod
    def get_cache_key(**kwargs) -> int:
        """
        Computes the cache key for the given keyword arguments.
        The implementation of this method must be deterministic;
        given a particular input, it must always produce the same output.
        """
        raise NotImplementedError

    @classmethod
    def get_or_create(cls, **kwargs) -> int:
        """
        This is similar to Model.get_ot_create but returns the `cache_key`
        (which is the `pk`) matching the potential instance without doing a database query.
        Later, the `resolve` method of `cls` must be called to actually
        get or/and create the corresponding instances in bulk.
        """
        if (
            cache_key := cls.get_cache_key(**kwargs)
        ) not in cls.resolved and cache_key not in cls.to_resolve:
            cls.to_resolve[cache_key] = cls(cache_key, **kwargs)
        return cache_key

    @cached_attribute
    def model(cls):
        """Model this promise class is attached to."""
        return apps.get_model(cls.model_string)

    @cached_attribute
    def base_queryset(cls):
        return cls.model.objects.all()

    @cached_attribute
    def queryset(cls):
        return cls.base_queryset.only("cache_key").values_list("cache_key", flat=True)

    @classmethod
    def obj_found(cls, cache_key):
        """
        Hook run when an object with the given `cache_key` is found in the database.
        """
        # Add the `cache_key` to `resolved`.
        cls.resolved.add(cache_key)
        # Remove and return the corresponding promise from `to_resolve`.
        return cls.to_resolve.pop(cache_key)

    # Hook run when an object with a given `cache_key` is created.
    obj_created = obj_found

    @classmethod
    @delay
    def resolve_existing(cls, to_resolve):
        """
        Finds all existing objects with primary keys matching the ones in `to_resolve`
        and resolves the corresponding promises.
        """
        obj_found = cls.obj_found
        for cache_key in cls.queryset.filter(cache_key__in=to_resolve).iterator():
            obj_found(cache_key)
            del to_resolve[cache_key]

    @classmethod
    @delay
    def resolve_new(cls, to_resolve):
        """
        Creates new model instances for the promises in `to_resolve`.
        """
        Model = cls.model
        created = cls.base_queryset.bulk_create(
            Model(cache_key=cache_key, **promise.creation_kwargs)
            for cache_key, promise in to_resolve.items()
        )

        obj_created = cls.obj_created
        for obj in created:
            obj_created(obj.cache_key)

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
    model_string = "dj_tracker.Model"

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, label: str) -> int:
        return hash_string(label)


class FieldPromise(Promise):
    model_string = "dj_tracker.Field"
    deps = (ModelPromise,)

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, model_id: int, name: str) -> int:
        return hash((model_id, hash_string(name)))


class SQLPromise(Promise):
    model_string = "dj_tracker.SQL"

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, sql: str) -> int:
        return hash_string(sql)


class URLPathPromise(Promise):
    model_string = "dj_tracker.URLPath"

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, path: str) -> int:
        return hash_string(path)


class SourceFilePromise(Promise):
    model_string = "dj_tracker.SourceFile"

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, name: str) -> int:
        return hash_string(name)


class SourceCodePromise(Promise):
    model_string = "dj_tracker.SourceCode"
    deps = (SourceFilePromise,)

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, filename_id: int, func: str, code: str, lineno: int) -> int:
        return hash((filename_id, hash_string(func), hash_string(code), lineno))


class StackPromise(Promise):
    model_string = "dj_tracker.Stack"
    deps = (SourceCodePromise,)

    stack_entries = []

    __slots__ = "entries"

    def __init__(self, cache_key: int, *, entries):
        super().__init__(cache_key)
        self.entries = entries

    @staticmethod
    def get_cache_key(*, entries) -> int:
        return hash(entries)

    @classmethod
    def obj_created(cls, cache_key: int) -> "StackPromise":
        """
        Adds new stack entries for save when a `Stack` instance is created.
        """
        from dj_tracker.models import StackEntry

        promise = super().obj_created(cache_key)
        cls.stack_entries.extend(
            StackEntry(stack_id=cache_key, index=index, source_id=source_code_id)
            for index, source_code_id in promise.entries
        )
        return promise

    @classmethod
    def resolve(cls):
        super().resolve()
        if stack_entries := cls.stack_entries:
            cls.create_stack_entries(stack_entries)

    @classmethod
    @delay
    def create_stack_entries(cls, stack_entries):
        from dj_tracker.models import StackEntry

        StackEntry.objects.bulk_create(stack_entries)
        stack_entries.clear()


class TracebackPromise(Promise):
    model_string = "dj_tracker.Traceback"
    deps = (StackPromise,)

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, top_id: int, middle_id: int, bottom_id: int) -> int:
        return hash((top_id, middle_id, bottom_id))

    @classmethod
    def get(cls, ignore_frames: int = 3) -> int:
        """
        Returns the current traceback id.
        """
        stack = []
        frame = _getframe(ignore_frames)
        get_source_code_id = SourceCodePromise.get_or_create
        get_source_file_id = SourceFilePromise.get_or_create

        try:
            while frame:
                code = frame.f_code
                filename = code.co_filename
                lineno = frame.f_lineno
                stack.append(
                    (
                        get_source_code_id(
                            func=code.co_name,
                            code=getline(filename, lineno),
                            lineno=lineno,
                            filename_id=get_source_file_id(name=filename),
                        ),
                        ignore_frame(filename),
                    )
                )
                frame = frame.f_back
        finally:
            del frame

        def ignore_entry(entry):
            return entry[1]

        top_entries = tuple(
            (i, entry[0]) for i, entry in enumerate(takewhile(ignore_entry, stack))
        )
        top_index = len(top_entries)
        bottom_entries = tuple(
            entry[0] for entry in takewhile(ignore_entry, reversed(stack[top_index:]))
        )
        bottom_entries = tuple(
            (i, entry) for i, entry in enumerate(reversed(bottom_entries))
        )
        middle_entries = tuple(
            (i, entry[0])
            for i, entry in enumerate(
                stack[top_index : len(stack) - len(bottom_entries)]
            )
        )

        get_stack_id = StackPromise.get_or_create
        return cls.get_or_create(
            top_id=get_stack_id(entries=top_entries),
            middle_id=get_stack_id(entries=middle_entries),
            bottom_id=get_stack_id(entries=bottom_entries),
        )


class FieldTrackingPromise(Promise):
    model_string = "dj_tracker.FieldTracking"
    deps = (FieldPromise,)

    __slots__ = ()

    @staticmethod
    def get_cache_key(*, field_id: int, get_count: int, set_count: int) -> int:
        return hash((field_id, get_count, set_count))


class InstanceTrackingPromise(Promise):
    model_string = "dj_tracker.InstanceTracking"
    deps = (FieldTrackingPromise,)

    trackings = []

    __slots__ = "field_trackings"

    def __init__(self, cache_key: int, *, field_trackings, **kwargs):
        super().__init__(cache_key, **kwargs)
        self.field_trackings = field_trackings

    @staticmethod
    def get_cache_key(*, field_trackings, select_related_field: str) -> int:
        return hash((field_trackings, hash_string(select_related_field)))

    @classmethod
    def obj_created(cls, cache_key: int) -> "InstanceTrackingPromise":
        """
        Adds new instance field trackings for save when
        an `InstanceTracking` instance is created.
        """
        from dj_tracker.models import InstanceFieldTracking

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
        if cls.trackings:
            cls.create_instance_field_trackings()

    @classmethod
    @delay
    def create_instance_field_trackings(cls):
        from dj_tracker.models import InstanceFieldTracking

        InstanceFieldTracking.objects.bulk_create(cls.trackings)
        cls.trackings.clear()


class QueryPromise(Promise):
    model_string = "dj_tracker.Query"
    deps = (TracebackPromise, SQLPromise, ModelPromise, InstanceTrackingPromise)

    trackings = []

    __slots__ = "instance_trackings"

    def __init__(self, cache_key: int, *, instance_trackings, **kwargs):
        super().__init__(cache_key, **kwargs)
        self.instance_trackings = instance_trackings

    @staticmethod
    def get_cache_key(
        *,
        depth: int,
        query_type: str,
        cache_hits: Optional[int],
        num_instances: int,
        iterable_class: Optional[str],
        instance_trackings: Tuple,
        attributes_accessed: Optional[Dict[str, int]],
        len_calls: int,
        exists_calls: int,
        contains_calls: int,
        sql_id: int,
        model_id: int,
        traceback_id: int,
        field_id: Optional[int],
        related_queryset_id: Optional[int],
    ) -> int:
        return hash(
            (
                depth,
                hash_string(query_type),
                cache_hits if cache_hits is not None else 0,
                num_instances,
                hash_string(iterable_class) if iterable_class else 0,
                instance_trackings,
                tuple(
                    (hash_string(attr), count)
                    for attr, count in attributes_accessed.items()
                )
                if attributes_accessed
                else 0,
                len_calls,
                exists_calls,
                contains_calls,
                sql_id,
                field_id if field_id else 0,
                model_id,
                traceback_id,
                related_queryset_id if related_queryset_id else 0,
            )
        )

    @classmethod
    def obj_created(cls, cache_key: int) -> "QueryPromise":
        promise = super().obj_created(cache_key)
        InstanceTracking = cls.model.instance_trackings.through
        cls.trackings.extend(
            InstanceTracking(
                query_id=cache_key,
                instancetracking_id=instance_tracking_id,
            )
            for instance_tracking_id in promise.instance_trackings
        )
        return promise

    @classmethod
    def resolve(cls):
        super().resolve()
        if trackings := cls.trackings:
            cls.create_instance_trackings(trackings)

    @classmethod
    @delay
    def create_instance_trackings(cls, trackings):
        cls.model.instance_trackings.through.objects.bulk_create(trackings)
        trackings.clear()


class QueryGroupPromise(Promise):
    model_string = "dj_tracker.QueryGroup"

    trackings = []
    to_update = set()
    durations = {}

    __slots__ = "queries"

    def __init__(self, cache_key: int, *, queries):
        super().__init__(cache_key)
        self.queries = queries

    def get_cache_key(*, queries) -> int:
        return hash(queries)

    @classmethod
    def get_or_create(cls, *, queries):
        cache_key = super().get_or_create(
            queries=tuple(sorted(Counter(query_id for query_id, _ in queries).items()))
        )

        if not (prev_durations := cls.durations.get(cache_key)):
            prev_durations = cls.durations[cache_key] = {}

        for query_id, duration in queries:
            if query_id in prev_durations:
                prev_durations[query_id] = prev_durations[query_id] + duration / 2
            else:
                prev_durations[query_id] = duration

        return cache_key

    @classmethod
    def obj_found(cls, cache_key: int) -> "QueryGroupPromise":
        cls.to_update.add(cache_key)
        return super().obj_found(cache_key)

    @classmethod
    def obj_created(cls, cache_key: int) -> "QueryGroupPromise":
        """
        Adds new queryset trackings for save when a `QueryGroup` instance is created.
        """
        from dj_tracker.models import QuerySetTracking

        promise = super().obj_created(cache_key)
        durations = cls.durations[cache_key]
        cls.trackings.extend(
            QuerySetTracking(
                query_id=query_id,
                query_group_id=cache_key,
                num_occurrences=num_occurrences,
                average_duration=durations[query_id],
            )
            for query_id, num_occurrences in promise.queries
        )
        return promise

    @classmethod
    def resolve(cls):
        super().resolve()
        if trackings := cls.trackings:
            cls.create_trackings(trackings)

        if to_update := cls.to_update:
            cls.update_durations(to_update)

    @classmethod
    @delay
    def create_trackings(cls, trackings):
        from dj_tracker.models import QuerySetTracking

        QuerySetTracking.objects.bulk_create(trackings)
        trackings.clear()

    @classmethod
    @delay
    def update_durations(cls, to_update):
        from dj_tracker.models import QuerySetTracking

        durations = cls.durations
        objs = QuerySetTracking.objects.filter(query_group_id__in=to_update)
        for qs_tracking in objs:
            qs_tracking.average_duration = (
                qs_tracking.average_duration
                + durations[qs_tracking.query_group_id][qs_tracking.query_id] / 2
            )

        QuerySetTracking.objects.bulk_update(objs, fields=["average_duration"])
        to_update.clear()
