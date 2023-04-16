import functools
import itertools
import linecache
import operator
import weakref
from collections import defaultdict
from sys import settrace, stdout
from time import perf_counter_ns as now
from types import MethodType


class profile:
    """
    Print per-line statistics for a function's calls when it's garbage collected.
    This is a lightweight alternative to https://github.com/pyutils/line_profiler;
    mostly for internal use.
    """

    def __init__(self, func):
        self.func = func
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
        filename = self.func.__code__.co_filename
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
