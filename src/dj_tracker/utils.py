from collections import Counter, OrderedDict
from functools import partial, reduce

try:
    from dj_tracker.speedups import hash_counter, hash_list, hash_string
except ImportError:

    def hash_string(
        string: str,
        hasher=lambda hash_value, char: (hash_value << 5) + hash_value + ord(char),
    ) -> int:
        # djb2: http://www.cse.yorku.ca/~oz/hash.html
        return hash(reduce(hasher, string, 5381))


class HashableMixin:
    __slots__ = ()

    def __hash__(self):
        return self.hash_value

    def __getattr__(self, name):
        if name == "hash_value":
            self.hash_value = hash_value = self.hash()
            return hash_value
        raise AttributeError

    def hash(self):
        raise NotImplementedError


class HashableList(HashableMixin, list):
    __slots__ = "hash_value"

    if "hash_list" in globals():

        def hash(self):
            return hash_list(self)

    else:

        def hash(self):
            result = 98767 - len(self) * 555
            for i, obj in enumerate(self):
                result = result + i + (hash(obj) % 9999999) * 1001
            return result


class HashableCounter(HashableMixin, Counter):
    __slots__ = "hash_value"

    if "hash_counter" in globals():

        def hash(self):
            return hash_counter(self)

    else:

        def hash(self):
            result = 98767 - len(self) * 555
            for key in sorted(self):
                result = result + self[key] + (hash(key) % 9999999) * 1001
            return result


class LRUBoundedDict(OrderedDict):
    def __init__(self, maxsize=256):
        super().__init__()
        self.maxsize = maxsize

    def get(
        self, key, default=None, dict_get=dict.get, move_to_end=OrderedDict.move_to_end
    ):
        if (value := dict_get(self, key, default)) is not default:
            move_to_end(self, key)
        return value

    def __setitem__(
        self,
        key,
        value,
        len=dict.__len__,
        odict_setitem=OrderedDict.__setitem__,
        odict_popfirst=partial(OrderedDict.popitem, last=False),
    ):
        odict_setitem(self, key, value)
        if len(self) > self.maxsize:
            odict_popfirst(self)


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
