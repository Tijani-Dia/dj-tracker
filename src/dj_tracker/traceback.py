from collections import defaultdict
from functools import lru_cache
from linecache import getline
from sys import _getframe

from django.template import Node

from dj_tracker.constants import IGNORED_MODULES
from dj_tracker.promise import SourceFilePromise
from dj_tracker.utils import HashableList, HashableMixin, hash_string


class TracebackEntry(HashableMixin):
    instances = defaultdict(dict)

    __slots__ = ("filename", "lineno", "func")

    def __new__(cls, filename, lineno, func=""):
        instances_for_file = cls.instances[filename]
        if not (self := instances_for_file.get(lineno)):
            instances_for_file[lineno] = self = object.__new__(cls)
            self.filename = filename
            self.lineno = lineno
            self.func = func
        return self

    def __getnewargs__(self):
        return (self.filename, self.lineno, self.func)

    def hash_value(self):
        return hash((self.filename, self.lineno))

    def code(self):
        return getline(self.filename, self.lineno).strip()

    def filename_id(self):
        return SourceFilePromise.get_or_create(name=self.filename)

    def cache_key(self):
        return hash(
            (
                self.filename_id,
                self.lineno,
                hash_string(self.code),
                hash_string(self.func),
            )
        )

    lazy_slots = (hash_value, code, filename_id, cache_key)


def get_traceback():
    frame = _getframe(3)
    stack = HashableList()
    template_info = None
    add_stack_entry = stack.append
    top_entries_found = False
    num_bottom_entries = 0

    try:
        while frame:
            code = frame.f_code
            if (func := code.co_name) == "render":
                node = frame.f_locals.get("self")
                if isinstance(node, Node):
                    try:
                        template_info = TracebackEntry(
                            node.origin.name, node.token.lineno
                        )
                    except AttributeError:
                        pass
                    else:
                        break

            filename = code.co_filename
            if ignore_file(filename):
                if top_entries_found:
                    add_stack_entry(TracebackEntry(filename, frame.f_lineno, func))
                    num_bottom_entries += 1
            else:
                if num_bottom_entries:
                    num_bottom_entries = 0
                elif not top_entries_found:
                    top_entries_found = True

                add_stack_entry(TracebackEntry(filename, frame.f_lineno, func))

            frame = frame.f_back
    finally:
        del frame

    if num_bottom_entries:
        stack[-num_bottom_entries:] = []

    return stack, template_info


@lru_cache(maxsize=None)
def ignore_file(filename: str) -> bool:
    """Indicates whether the frame containing the given filename should be ignored."""
    return any(module in filename for module in IGNORED_MODULES)
