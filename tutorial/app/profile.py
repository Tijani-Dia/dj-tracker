import atexit
import tracemalloc
from time import perf_counter_ns


class Profiler:
    def __init__(self, func):
        self.func = func
        self.ncalls = 0
        atexit.register(self.report)

    @staticmethod
    def print_stats(name, stats, ncalls):
        if ncalls == 0:
            return

        print(  # noqa
            "\n{} ({} calls) - Min: {:.2f}, Max: {:.2f}, Avg: {:.2f}".format(
                name, ncalls, min(stats), max(stats), sum(stats) / len(stats)
            )
        )


class TimeProfiler(Profiler):
    def __init__(self, func):
        super().__init__(func)
        self.times = []

    def __call__(self, *args, **kwargs):
        now = perf_counter_ns()

        result = self.func(*args, **kwargs)

        self.times.append((perf_counter_ns() - now) * 1e-6)
        self.ncalls += 1
        return result

    def report(self):
        self.print_stats("Time in ms", self.times, self.ncalls)


class MemoryProfiler(Profiler):
    def __init__(self, func):
        super().__init__(func)
        self.sizes = []
        self.peaks = []

    def __call__(self, *args, **kwargs):
        tracemalloc.start()

        result = self.func(*args, **kwargs)

        size, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.sizes.append(size / 1024)
        self.peaks.append(peak / 1024)
        self.ncalls += 1
        return result

    def report(self):
        self.print_stats("Memory - size in KiB", self.sizes, self.ncalls)
        self.print_stats("Memory - peak in KiB", self.peaks, self.ncalls)
