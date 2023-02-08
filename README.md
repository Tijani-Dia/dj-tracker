<p align="center">
    <a href="https://github.com/tijani-dia/dj-tracker/actions/workflows/test.yml">
        <img src="https://github.com/tijani-dia/dj-tracker/actions/workflows/test.yml/badge.svg"/>
    </a>
    <a href="https://codecov.io/gh/Tijani-Dia/dj-tracker">
        <img src="https://codecov.io/gh/Tijani-Dia/dj-tracker/branch/main/graph/badge.svg?token=MKJ71ZJE67"/>
    </a>
    <a href="https://pypi.org/project/django-trackings/">
        <img src="https://badge.fury.io/py/django-trackings.svg" alt="Package version">
    </a>
    <a href="https://pypistats.org/packages/django-trackings">
        <img src="https://img.shields.io/pypi/dm/django-trackings?logo=Downloads" alt="Monthly downloads"/>
    </a>
    <a href="https://opensource.org/licenses/BSD-3-Clause">
        <img src="https://img.shields.io/badge/license-BSD-blue.svg"/>
    </a>
</p>

`dj-tracker` is an app that tracks your queries to help detecting some possible performance optimisations listed in [Database access optimization](https://docs.djangoproject.com/en/dev/topics/db/optimization/).

## Features

-   Detailed field usage of model instances
-   Report unused fields in a model instance and provides hints on when to use `.defer` and `.only`
-   Report model instance attributes access and provides hints on when to use `.values` or `.values_list`
-   Report cache hits and provides hints on when to use `iterator`
-   Provides hints on when to use `.count`, `.contains`, `.exists`
-   Detect N+1 queries
-   Detect when a deferred field is loaded
-   and many more insights into your queries with minimized overhead....

## Requirements

-   Python: `>=3.8`
-   Django: `>=3.2`

## Getting started

Check out the [installation steps](https://tijani-dia.github.io/dj-tracker/installation/).

## Documentation

All documentation is in the "docs" directory and online at https://tijani-dia.github.io/dj-tracker/

## Development phase

`dj-tracker` is in [alpha phase](https://en.wikipedia.org/wiki/Software_release_life_cycle#Alpha).

## Contributing

The best way you can help, at this stage, is to install it and report bugs you'll encounter.

Feature requests, PRs and feedbacks are welcome.
