from cpython.dict cimport PyDict_Next
from cpython.object cimport PyObject


cdef class LRUCache:
    def __cinit__(self, int maxsize=256):
        self.cache = {}
        self.maxsize = maxsize

    cpdef get(self, key):
        if (value := self.cache.pop(key, None)) is not None:
            self.cache[key] = value
            return value
    
    cpdef void set(self, key, value):
        cdef:
            PyObject *lru_key
            Py_ssize_t pos = 0
            dict cache = self.cache

        if len(cache) == self.maxsize:
            PyDict_Next(cache, &pos, &lru_key, NULL)
            del cache[<object>lru_key]

        cache[key] = value
    
    def __len__(self):
        return len(self.cache)

    def __repr__(self):
        return f"LRUCache({self.cache})"


class LazySlots(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        if lazy_slots := namespace.get("lazy_slots"):
            lazy_slots = {
                name: namespace.pop(name)
                for name, meth in tuple(namespace.items())
                if meth in lazy_slots
            }

            def __getattr__(self, attr, dict lazy_slots=lazy_slots):
                if (method := lazy_slots.get(attr)) is not None:
                    result = method(self)
                    setattr(self, attr, result)
                    return result

                raise AttributeError(attr)

            namespace.update(
                __getattr__=__getattr__,
                __slots__=(*namespace.get("__slots__", ()), *lazy_slots),
            )

        return super().__new__(cls, name, bases, namespace, **kwargs)


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
