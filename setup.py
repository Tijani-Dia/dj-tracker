import os
import subprocess

from setuptools import Command, Extension, setup
from setuptools.command.build_py import build_py as BuildCommand
from setuptools.command.sdist import sdist as SDistCommand

SKIP_TAILWIND = os.getenv("SKIP_TAILWIND")
TRACE_LINES = os.getenv("TRACE_LINES")
MACROS = [("CYTHON_TRACE", 1 if TRACE_LINES else 0)]


extensions = [
    Extension(
        "dj_tracker.cache_utils",
        sources=["src/dj_tracker/cache_utils.pyx"],
        define_macros=MACROS,
    ),
    Extension(
        "dj_tracker.hash_utils",
        sources=["src/dj_tracker/hash_utils.pyx"],
        define_macros=MACROS,
    ),
    Extension(
        "dj_tracker.traceback",
        sources=["src/dj_tracker/traceback.pyx"],
        define_macros=MACROS,
    ),
]

try:
    from Cython.Build import cythonize
except ImportError:
    SKIP_TAILWIND = True
else:
    extensions = cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "linetrace": True if TRACE_LINES else False,
        },
    )


class CompilePyxCommand(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.announce("Compiling .pyx files")
        subprocess.run(
            ["cython", "src/dj_tracker/*pyx", "-3"], stderr=subprocess.STDOUT
        )


class TailwindCommand(Command):
    user_options = []

    def initialize_options(self):
        self.output_file = ""

    def finalize_options(self):
        if self.output_file:
            assert os.path.exists(self.output_file)

    def run(self):
        if SKIP_TAILWIND:
            return

        self.output_file = "src/dj_tracker/static/dj_tracker/css/main.css"
        self.announce("Compiling styles with Tailwind")

        try:
            p = subprocess.run(
                [
                    "tailwindcss",
                    "-i",
                    "styles/main.css",
                    "-o",
                    self.output_file,
                    "--minify",
                ],
                stderr=subprocess.STDOUT,
            )
            p.check_returncode()
        except (OSError, subprocess.CalledProcessError) as e:
            self.warn(f"Error compiling styles: {str(e)}")
            raise SystemExit(1)


class DjTrackerSDistCommand(SDistCommand):
    def run(self):
        self.run_command("compile_pyx")
        self.run_command("tailwind")
        SDistCommand.run(self)


class DjTrackerBuildCommand(BuildCommand):
    def run(self):
        self.run_command("tailwind")
        BuildCommand.run(self)


setup(
    ext_modules=extensions,
    cmdclass={
        "sdist": DjTrackerSDistCommand,
        "build_py": DjTrackerBuildCommand,
        "tailwind": TailwindCommand,
        "compile_pyx": CompilePyxCommand,
    },
)
