from collections import Counter
from functools import reduce

from dj_tracker.utils import LazySlots

try:
    from dj_tracker.speedups import hash_counter, hash_list, hash_string
except ImportError:

    def hash_string(
        string: str,
        hasher=lambda hash_value, char: (hash_value << 5) + hash_value + ord(char),
    ) -> int:
        # djb2: http://www.cse.yorku.ca/~oz/hash.html
        return hash(reduce(hasher, string, 5381))


class HashableMixin(metaclass=LazySlots):
    __slots__ = ()

    def __hash__(self):
        return self.hash_value


class HashableList(HashableMixin, list):
    if "hash_list" in globals():

        def hash_value(self):
            return hash_list(self)

    else:

        def hash_value(self):
            result = 98767 - len(self) * 555
            for i, obj in enumerate(self):
                result = result + i + (hash(obj) % 9999999) * 1001
            return result

    lazy_slots = (hash_value,)


class HashableCounter(HashableMixin, Counter):
    if "hash_counter" in globals():

        def hash_value(self):
            return hash_counter(self)

    else:

        def hash_value(self):
            result = 98767 - len(self) * 555
            for key in sorted(self):
                result = result + self[key] + (hash(key) % 9999999) * 1001
            return result

    lazy_slots = (hash_value,)
