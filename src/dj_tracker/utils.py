from collections import OrderedDict


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


class LRUBoundedDict(OrderedDict):
    def __init__(self, maxsize=256):
        super().__init__()
        self.maxsize = maxsize

    def get(self, key, dict_get=dict.get, move_to_end=OrderedDict.move_to_end):
        if value := dict_get(self, key):
            move_to_end(self, key)
        return value

    def __setitem__(
        self,
        key,
        value,
        len=dict.__len__,
        odict_popitem=OrderedDict.popitem,
        odict_setitem=OrderedDict.__setitem__,
    ):
        odict_setitem(self, key, value)
        if len(self) > self.maxsize:
            odict_popitem(self, False)


class LazySlots(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        if lazy_slots := namespace.get("lazy_slots"):
            lazy_slots = {
                name: namespace.pop(name)
                for name, meth in tuple(namespace.items())
                if meth in lazy_slots
            }
            get_method_for_slot = lazy_slots.get
            set_attr = setattr

            def __getattr__(self, attr):
                if method := get_method_for_slot(attr):
                    result = method(self)
                    set_attr(self, attr, result)
                    return result

                raise AttributeError

            namespace.update(
                __getattr__=__getattr__,
                __slots__=(*namespace.get("__slots__", ()), *lazy_slots),
            )

        return super().__new__(cls, name, bases, namespace, **kwargs)
