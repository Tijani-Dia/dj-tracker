import functools
import itertools
import linecache
import operator
import weakref
from collections import OrderedDict, defaultdict
from sys import settrace, stdout
from time import perf_counter_ns as now
from types import MethodType


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


class profile:
    """
    Print per-line statistics for a function's calls when it's garbage collected.
    This is a lightweight alternative to https://github.com/pyutils/line_profiler;
    mostly for internal use.
    """

    def __init__(self, func):
        self.func = func
        self.filename = func.__code__.co_filename
        self.calls = defaultdict(list)
        self.ncalls = 0
        self.time = self.curr_line = None
        functools.update_wrapper(self, func)
        weakref.finalize(func, self.print_stats)

    def __get__(self, instance, cls):
        if instance is None:
            return self
        return MethodType(self, instance)

    def __call__(self, *args, **kwargs):
        self.ncalls += 1
        settrace(self.trace_new_call)
        try:
            return self.func(*args, **kwargs)
        finally:
            settrace(None)

    def trace_new_call(self, frame, event, arg):
        settrace(self.skip_trace)
        return self.trace_lines

    def skip_trace(self, frame, event, arg):
        return

    def trace_lines(self, frame, event, arg):
        if event == "line":
            if self.curr_line:
                self.calls[self.curr_line].append(now() - self.time)
            self.curr_line = frame.f_lineno
            self.time = now()
            return self.trace_lines
        elif event == "return":
            self.calls[self.curr_line].append(now() - self.time)
            self.time = self.curr_line = None

    def print_stats(self):
        write = stdout.write
        get_line = linecache.getline
        template = "{:<10} {:<16.2f} {:<6.2%} {}\n"

        total_time = sum(itertools.chain.from_iterable(self.calls.values()))
        write(
            "\n{}: {} calls, {:.2f}ms\n".format(
                self.func, self.ncalls, total_time * 1e-6
            )
        )
        write("\n{:<10} {:<16} {:<6}\n".format("Num hits", "Per hit(1e-6s)", "%"))
        write("{:<10} {:<16} {:<6}\n".format("--------", "--------------", "-----"))

        prev_lineno = None
        filename = self.filename
        for lineno, data in sorted(self.calls.items(), key=operator.itemgetter(0)):
            if prev_lineno:
                while prev_lineno + 1 < lineno:
                    prev_lineno += 1
                    line = get_line(filename, prev_lineno)
                    if line.strip():
                        write(template.format(0, 0, 0, line))

            prev_lineno = lineno
            num_hits = len(data)
            line_time = sum(data)
            write(
                template.format(
                    num_hits,
                    (line_time * 1e-3) / num_hits,
                    line_time / total_time,
                    get_line(filename, lineno).rstrip(),
                )
            )
