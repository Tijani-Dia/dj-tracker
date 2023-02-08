import os

from setuptools import Extension, setup

TRACE_LINES = os.getenv("TRACE_LINES")
MACROS = [("CYTHON_TRACE", 1 if TRACE_LINES else 0)]


extensions = [
    Extension(
        f"dj_tracker.{module}",
        sources=[f"src/dj_tracker/{module}.pyx"],
        define_macros=MACROS,
    )
    for module in ("cache_utils", "hash_utils", "traceback")
]

try:
    from Cython.Build import cythonize
except ImportError:
    pass
else:
    extensions = cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "linetrace": True if TRACE_LINES else False,
        },
    )

setup(ext_modules=extensions)
