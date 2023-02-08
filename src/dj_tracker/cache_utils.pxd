cdef class LRUCache:
    cdef dict cache
    cdef readonly int maxsize

    cpdef get(self, key)
    cpdef void set(self, key, value)
