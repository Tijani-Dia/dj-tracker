from collections import Counter

from dj_tracker.utils import LazySlots


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
    cdef:
        int i, n = len(string)
        unsigned long hash_value = 5381
        bytes as_bytes = string.encode('UTF-8')
        const unsigned char* as_c_string = as_bytes

    for i in range(n):
        hash_value += (hash_value << 5) + as_c_string[i]

    return hash_value


cdef int hash_list(list l):
    cdef:
        int i, n = len(l)
        unsigned long hash_value = 98767 - n * 555

    for i in range(n):
        hash_value += (hash(l[i]) % 9999999) * 1001 + i

    return hash_value


cdef int hash_counter(dict counter):
    cdef:
        int value, i, n = len(counter)
        unsigned long hash_value = 98767 - n * 555
        list keys = sorted(counter)
        object key

    for i in range(n):
        key = keys[i]
        value = counter[key]
        hash_value += (hash(key) % 9999999) * 1001 + value

    return hash_value
