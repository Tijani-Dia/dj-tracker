from functools import lru_cache, wraps
from time import sleep
from uuid import uuid5

from django.core.exceptions import EmptyResultSet, FieldError
from django.db.models.sql import Query

from dj_tracker.constants import IGNORED_MODULES, NAMESPACE, STOPPING


@lru_cache
def hash_string(string: str) -> int:
    # This addresses Python built-in's string hashing algorithm
    # not being persistent accross different processes.
    return hash(uuid5(NAMESPACE, string).int)


@lru_cache
def ignore_frame(filename: str) -> bool:
    """
    Indicates whether the frame containing the given filename
    should be ignored.
    """
    return any(module in filename for module in IGNORED_MODULES)


def get_sql_from_query(query: Query) -> str:
    """
    Returns the SQL generated for the given query if possible.
    """
    try:
        return str(query)
    except (TypeError, ValueError, FieldError, EmptyResultSet):
        return ""


def delay(func):
    """
    Decorator that delays the execution of `func` for 1s while the worker thread is running.
    This avoids bloating the database when we save the trackings.
    """
    stopping = STOPPING.is_set

    @wraps(func)
    def wrapper(*args, **kwargs):
        if sleep_for := 1 if not stopping() else 0:
            sleep(sleep_for)
        return func(*args, **kwargs)

    return wrapper


class cached_attribute:
    """
    This is similar to `cached_property` but for classes rather than class instances.
    """

    def __init__(self, func):
        self.func = func

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, cls):
        if not cls:
            cls = type(instance)

        result = self.func(cls)
        setattr(cls, self.name, result)
        return result
