# Installation

## Install the package

Install `django-trackings` from PyPi:

```bash
pip install django-trackings
```

## Add `dj_tracker` to `INSTALLED_APPS`

Add `dj_tracker` to your `INSTALLED_APPS` in your settings:

```python
INSTALLED_APPS = [
    ...
    "dj_tracker",
    ...
]
```

## Add `dj_tracker` middleware

Add `DjTrackerMiddleware` to the `MIDDLEWARE` list in your project's settings:

```python
MIDDLEWARE = [
    "dj_tracker.middleware.DjTrackerMiddleware",
    ...
]
```

## Add `dj_tracker` URLs

Add the following to your `urls.py` file:

```python
from dj_tracker.urls import urlpatterns as dj_tracker_urls


urlpatterns = [
    ...
    path("dj-tracker/", include(dj_tracker_urls)),
    ...
]
```

## Add additional configuration to `manage.py`

`dj_tracker` does a lot of job in a background thread to limit the overhead incurred by its usage. As such, it's important to stop the background thread when your program exits otherwise some trackings may not be saved. A good place to do it is in the `manage.py` which is often the main entrypoint of Django programs.

```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

    from django.core.management import execute_from_command_line

    try:
        execute_from_command_line(sys.argv)
    finally:
        if os.environ.get("DEBUG", "true").lower() == "true":
            from dj_tracker import tracker

            tracker.stop()
```

**Note**: Your `manage.py` file doesn't need to exactly look like that. The important part is to call `tracker.stop()` depending on when the tracker is run. In the above example, we assume that `dj_tracker` is installed whenever the environment variable `DEBUG` is set to `true`.

**Note**: There is no harm in calling `tracker.stop` when the background thread isn't running; nothing will happen.

## There we go

Your Django models are now ready to be tracked!

Run the `runserver` command with the `--noreload` option (**important**) and your trackings will be available at `/dj_tracker/`.

Have a look at the [Usage page](./usage.md) to learn more about how to use `dj_tracker` to optimise your queries.

There are also [more configuration options available](./configuration.md).
