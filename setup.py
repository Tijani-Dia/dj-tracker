import os

from setuptools import Extension, find_packages, setup

from Cython.Build import cythonize  # isort: skip


__version__ = "0.2.0a0"


TRACE_LINES = os.environ.get("TRACE_LINES")

extensions = [
    Extension(
        "*",
        sources=["src/dj_tracker/*.pyx"],
        define_macros=[("CYTHON_TRACE", 1 if TRACE_LINES else 0)],
    ),
]


with open("README.md", "r") as fh:
    long_description = fh.read()


install_requires = [
    "django>=3.2",
]

test_requires = [
    "black",
    "isort",
    "flake8",
    "factory_boy",
    "autoflake",
]

docs_requires = [
    "mkdocs",
    "mkdocs-material",
]


setup(
    name="django-trackings",
    version=__version__,
    description="A Django app that tracks your queries and helps optimizing them.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Tidiane Dia",
    author_email="atdia97@gmail.com",
    url="https://github.com/tijani-dia/dj-tracker/",
    project_urls={
        "Documentation": "https://tijani-dia.github.io/dj-tracker/",
        "Source": "https://github.com/tijani-dia/dj-tracker/",
        "Issue tracker": "https://github.com/tijani-dia/dj-tracker/issues/",
    },
    install_requires=install_requires,
    tests_require=test_requires,
    extras_require={
        "test": test_requires,
        "docs": docs_requires,
    },
    package_dir={"": "src"},
    packages=find_packages("src"),
    ext_modules=cythonize(
        extensions,
        annotate=False,
        compiler_directives={
            "language_level": 3,
            "linetrace": True if TRACE_LINES else False,
        },
    ),
    include_package_data=True,
    zip_safe=False,
    license="BSD-3-Clause",
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Framework :: Django",
    ],
)
