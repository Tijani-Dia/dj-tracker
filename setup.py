import os
from subprocess import STDOUT, CalledProcessError, check_call

from setuptools import Command, Extension, setup
from setuptools.command.build_py import build_py as BuildCommand
from setuptools.command.sdist import sdist as SDistCommand

from Cython.Build import cythonize  # isort: skip
from Cython.Compiler import Options  # isort: skip


Options.cimport_from_pyx = True

TRACE_LINES = os.getenv("TRACE_LINES")


class TailwindCommand(Command):
    user_options = []

    def initialize_options(self):
        self.output_file = ""

    def finalize_options(self):
        if self.output_file:
            assert os.path.exists(self.output_file)

    def run(self):
        if os.getenv("SKIP_TAILWIND"):
            return

        self.output_file = "src/dj_tracker/static/dj_tracker/css/main.css"
        self.announce("Compiling styles with Tailwind")

        try:
            check_call(
                [
                    "tailwindcss",
                    "-i",
                    "styles/main.css",
                    "-o",
                    self.output_file,
                    "--minify",
                ],
                stderr=STDOUT,
            )
        except (OSError, CalledProcessError) as e:
            self.warn(f"Error compiling styles: {str(e)}")
            raise SystemExit(1)


class DjTrackerSDistCommand(SDistCommand):
    def run(self):
        self.run_command("tailwind")
        SDistCommand.run(self)


class DjTrackerBuildCommand(BuildCommand):
    def run(self):
        self.run_command("tailwind")
        BuildCommand.run(self)


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
    cmdclass={
        "sdist": DjTrackerSDistCommand,
        "build_py": DjTrackerBuildCommand,
        "tailwind": TailwindCommand,
    },
)
