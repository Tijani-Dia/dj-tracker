# Configuration

## `dj_tracker` settings

All `dj_tracker` settings must be defined in a dictionary named `DJ_TRACKER` in your project's settings.

### `COMMANDS`

This setting determines the set of commands for which you'd like your queries to be tracked whenever they're run. The logic is encapsulated [here](https://github.com/Tijani-Dia/django-tracker/blob/main/src/dj_tracker/apps.py#L10). Should you have a different setup/need (for example running the tracker for a script), you can just make sure to call `tracker.start()` when your program starts.

```python
# settings.py

DJ_TRACKER = {
    "COMMANDS": {"runserver", "test"},
}
```

### `APPS_TO_EXCLUDE`

By default, `dj_tracker` tracks all models in all apps except from `dj_tracker` itself and the `sessions` app.
You can add additionnal apps to exclude with this setting:

```python
DJ_TRACKER = {
    "APPS_TO_EXCLUDE": {"third-party-app", "test-app"},
}
```

### `IGNORE_MODULES`

A set of file or module names to ignore in tracebacks.

```python
DJ_TRACKER = {
    "IGNORE_MODULES": {"some_app", "lib/module"}
}
```

### `COLLECTION_INTERVAL`

Interval at which the `Collector` should save trackings. The default value is `3ms`.

```python
DJ_TRACKER = {
    "COLLECTION_INTERVAL": 1
}
```

## `trackings` database

`dj_tracker` gives the possibility to have a separate table to store trackings. This can be useful if you intend to run it with your tests but also to track model instances in different databases(`staging`, `production`, ...).

### Add the database

Add a `trackings` entry to your `DATABASES` settings:

```python
DATABASES = {
    "default": ...,
    "trackings": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "trackings"),
    },
}
```

The examples uses a `sqlite` database but you can use any engine.

### Add the database router

Add the following to the list of `DATABASE_ROUTERS`:

```python
DATABASE_ROUTERS = [
    ...,
    "dj_tracker.db_router.DjTrackerRouter",
]
```
