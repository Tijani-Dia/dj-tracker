import os

from setuptools import Extension, setup

from Cython.Build import cythonize  # isort: skip
from Cython.Compiler import Options  # isort: skip


Options.cimport_from_pyx = True

TRACE_LINES = os.getenv("TRACE_LINES")


setup(
    ext_modules=cythonize(
        [
            Extension(
                "*",
                sources=["src/dj_tracker/*.pyx"],
                define_macros=[("CYTHON_TRACE", 1 if TRACE_LINES else 0)],
            ),
        ],
        annotate=False,
        compiler_directives={
            "language_level": 3,
            "linetrace": True if TRACE_LINES else False,
        },
    ),
)
