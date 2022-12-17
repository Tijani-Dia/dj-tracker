from setuptools import find_packages, setup

__version__ = "0.0.1a"

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
]

docs_requires = [
    "mkdocs",
    "mkdocs-material",
]

build_requires = [
    "twine",
    "check-wheel-contents",
]

setup(
    name="django-trackings",
    version=__version__,
    description="Track your Django models.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Tidiane Dia",
    author_email="atdia97@gmail.com",
    url="https://github.com/tijani-dia/django-tracker/",
    project_urls={
        "Documentation": "https://tijani-dia.github.io/django-tracker/",
        "Source": "https://github.com/tijani-dia/django-tracker/",
        "Issue tracker": "https://github.com/tijani-dia/django-tracker/issues/",
    },
    install_requires=install_requires,
    tests_require=test_requires,
    extras_require={
        "test": test_requires,
        "docs": docs_requires,
        "build": build_requires,
    },
    package_dir={"": "src"},
    packages=find_packages("src"),
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
