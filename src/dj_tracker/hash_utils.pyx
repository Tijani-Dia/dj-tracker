# cython: c_string_type=str, c_string_encoding=default

from collections import Counter

from dj_tracker.cache_utils import LazySlots


class HashableMixin(metaclass=LazySlots):
    __slots__ = ()

    def __hash__(self):
        return self.hash_value


class HashableList(HashableMixin, list):
    def hash_value(self):
        return hash_list(<list>self)

    lazy_slots = (hash_value,)


class HashableCounter(HashableMixin, Counter):
    def hash_value(self):
        return hash_counter(<dict>self)

    lazy_slots = (hash_value,)


cpdef int hash_string(str string):
    # djb2: http://www.cse.yorku.ca/~oz/hash.html.
    cdef:
        size_t i, n = len(string)
        unsigned long hash_value = 5381
        const unsigned char *as_c_string = string

    for i in range(n):
        hash_value += (hash_value << 5) + as_c_string[i]

    return hash_value


cdef int hash_list(list l):
    # See section on list hashing:
    # https://docs.python.org/3/faq/design.html#how-are-dictionaries-implemented-in-cpython.
    cdef:
        size_t i, n = len(l)
        unsigned long hash_value = 98767 - n * 555

    for i in range(n):
        hash_value += (hash(l[i]) % 9999999) * 1001 + i

    return hash_value


cdef int hash_counter(dict counter):
    cdef:
        size_t i, n = len(counter)
        unsigned long value, hash_value = 98767 - n * 555
        list keys = sorted(counter)

    for i in range(n):
        key = keys[i]
        value = counter[key]
        hash_value += (hash(key) % 9999999) * 1001 + value

    return hash_value
