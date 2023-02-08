cimport cython
from cpython.object cimport PyObject
from cpython.pystate cimport PyFrameObject

import os
import sys
from linecache import getline

from django.template import Node

from dj_tracker.cache_utils cimport LRUCache

from dj_tracker.constants import IGNORED_MODULES
from dj_tracker.hash_utils import HashableList, hash_string
from dj_tracker.promise import SourceFilePromise


cdef extern from "Python.h":
    void Py_INCREF(PyObject*)
    void Py_DECREF(PyObject*)

    ctypedef struct PyCodeObject:
        PyObject *co_filename
        PyObject *co_name

    PyFrameObject *PyEval_GetFrame()
    int PyFrame_GetLineNumber(PyFrameObject*)


cdef extern from "pythoncapi_compat.h":
    PyFrameObject *PyFrame_GetBack(PyFrameObject*)
    PyCodeObject *PyFrame_GetCode(PyFrameObject*)
    PyObject *PyFrame_GetGlobals(PyFrameObject*)
    PyObject *PyFrame_GetVar(PyFrameObject*, PyObject*)


@cython.freelist(512)
cdef class TracebackEntry:
    cdef:
        readonly str filename
        readonly str rel_path
        readonly int lineno
        readonly str func

        bint ignore
        bint is_render

        int hash_value

    def __init__(self, str filename, str rel_path, bint ignore, int lineno, str func):
        self.filename = filename
        self.rel_path = rel_path
        self.ignore = ignore
        self.lineno = lineno
        self.func = func
        self.is_render = func == "render"

    @property
    def filename_id(self):
        return SourceFilePromise.get_or_create(name=self.rel_path)

    @property
    def code(self):
        return getline(self.filename, self.lineno).strip()

    @property
    def cache_key(self):
        return hash(
            (
                self.filename_id,
                self.lineno,
                hash_string(self.code),
                hash_string(self.func),
            )
        )
    
    def __getattr__(self, name):
        if name == "hash_value":
            self.hash_value = hash((self.rel_path, self.lineno))
            return self.hash_value

        raise AttributeError(name)


cdef tuple get_file_info(str filename, PyFrameObject *frame, dict cache = {}):
    """Retrieves the relative path for a filename and indicates if it should be ignored."""
    cdef:
        str rel_path
        bint ignore

    try:
        return cache[filename]
    except KeyError:
        try:
            module_dir = next(path for path in sys.path if filename.startswith(path))
        except StopIteration:
            # The following logic is inspired from:
            # https://github.com/scoutapp/scout_apm_python/blob/master/src/scout_apm/core/backtrace.py#L29
            f_globals = PyFrame_GetGlobals(frame)
            module = (<dict>f_globals).get("__name__", "")
            Py_DECREF(f_globals)

            if (root_module := sys.modules.get(module.split(".", 1)[0])) is not None:
                if module_path := root_module.__file__:
                    module_dir = module_path.rsplit(os.sep, 2)[0]
                elif (module_path := root_module.__path__) and isinstance(module_path, (list, tuple)):
                    module_dir = module_path[0].rsplit(os.sep, 1)[0]
            else:
                # Fall back to current working directory.
                module_dir = os.getcwd()

        rel_path = os.path.relpath(filename, module_dir)
        ignore = any(module in filename for module in IGNORED_MODULES)
        cache[filename] = file_info = rel_path, ignore
        return file_info


cdef inline TracebackEntry get_entry(
    str filename,
    object lineno,
    PyFrameObject *frame,
    PyCodeObject *code = NULL,
    LRUCache cache = LRUCache(maxsize=512)
):
    cdef TracebackEntry entry
    cache_key = filename, lineno

    if (entry := cache.get(cache_key)) is None:
        entry = TracebackEntry(
            filename,
            *get_file_info(filename, frame),
            lineno,
            <object>code.co_name if code else "",
        )
        cache.set(cache_key, entry)

    return entry


cpdef tuple get_traceback():
    cdef:
        PyFrameObject *frame
        PyFrameObject *last_frame
        PyCodeObject *code
        PyObject *node
        TracebackEntry entry
        str self_var = "self"
        bint top_entries_found = False
        int num_bottom_entries = 0
        list stack = <list>HashableList()
        object template_info = None

    if not (last_frame := PyEval_GetFrame()):
        return (), None

    Py_INCREF(<PyObject*>last_frame)

    while frame := PyFrame_GetBack(last_frame):
        Py_DECREF(<PyObject*>last_frame)
        last_frame = frame

        code = PyFrame_GetCode(frame)
        entry = get_entry(<object>code.co_filename, PyFrame_GetLineNumber(frame), frame, code)
        Py_DECREF(<PyObject*>code)

        if template_info is None and entry.is_render:
            # This logic is inspired from:
            # https://github.com/jazzband/django-debug-toolbar/blob/main/debug_toolbar/utils.py#L123-L127
            try:
                node = PyFrame_GetVar(frame, <PyObject*>self_var)
            except NameError:
                pass
            else:
                node_obj = <object>node
                if isinstance(node_obj, Node):
                    template_info = get_entry(node_obj.origin.name, node_obj.token.lineno, frame)
                Py_DECREF(node)

        if entry.ignore:
            if top_entries_found:
                stack.append(entry)
                num_bottom_entries += 1
        else:
            if num_bottom_entries:
                num_bottom_entries = 0
            elif not top_entries_found:
                top_entries_found = True

            stack.append(entry)

    Py_DECREF(<PyObject*>last_frame)

    if num_bottom_entries:
        stack[-num_bottom_entries:] = []

    return stack, template_info
