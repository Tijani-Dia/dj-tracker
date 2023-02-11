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

## Run migrations

Run the migrations for the `dj_tracker` app:

```shell
python manage.py migrate dj_tracker
```

## There we go

Your Django models are now ready to be tracked!

Run the `runserver` command with the `--noreload` option (**important**) and your trackings will be available at `/dj-tracker/`.

Have a look at the [Tutorial page](./tutorial/setup.md) to learn more about how to use `dj_tracker` to optimise your queries or see the [configuration options available](./configuration.md).
