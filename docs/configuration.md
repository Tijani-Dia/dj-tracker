# Configuration

## `dj_tracker` settings

All `dj_tracker` settings must be defined in a dictionary named `DJ_TRACKER` in your project's settings.

### `APPS_TO_EXCLUDE`

By default, `dj_tracker` tracks all models in all apps except from `dj_tracker` itself.
You can add additionnal apps to exclude with this setting:

```python
DJ_TRACKER = {
    "APPS_TO_EXCLUDE": {"third-party-app", "test-app"},
}
```

### `IGNORE_PATHS`

Requests to URLs containing any component defined in this setting aren't tracked.

```python
DJ_TRACKER = {
    "IGNORE_PATHS": {"/favicon.ico", "/static/"}
}
```

### `IGNORE_MODULES`

A set of file or module names to ignore in tracebacks.

```python
DJ_TRACKER = {
    "IGNORE_MODULES": {"whitenoise/", "sentry_sdk/"}
}
```

### `COLLECTION_INTERVAL`

Interval at which the `Collector` should save trackings. The default value is `5s`.

```python
DJ_TRACKER = {
    "COLLECTION_INTERVAL": 1
}
```

### `FIELD_DESCRIPTORS`

If your program uses custom field descriptors, you can specify the path to the descriptor to use when tracking fields of that type. It can simply be the built-in [`EditableFieldDescriptor`](https://github.com/Tijani-Dia/dj-tracker/blob/main/src/dj_tracker/field_descriptors.py#L71) but can also be any subclass of [`FieldDescriptor`](https://github.com/Tijani-Dia/dj-tracker/blob/main/src/dj_tracker/field_descriptors.py#L6) provided that it's a data descriptor (i.e implements the `__set__` method).

For example, Wagtail defines a [`Creator`](https://github.com/wagtail/wagtail/blob/4246c0b703bccc9aafb6f86524bbbdb55c3c9e1e/wagtail/fields.py#L64) descriptor for its StreamField that can be tracked as follows:

```python
DJ_TRACKER = {
    "FIELD_DESCRIPTORS": {
        "Creator": "dj_tracker.field_descriptors.EditableFieldDescriptor"
    }
}
```

## `TRACK_ATTRIBUTES_ACCESSED`

`dj-tracker` patches the `__getattribute__` method on tracked models to provide hints on using `values` or `values_list` when it detects that no model attribute or method was accessed except the fields fetched from the database. This add an overhead to every attribute access. To disable this feature, set this setting to `False`. It's enabled by default.

```python
DJ_TRACKER = {
    "TRACK_ATTRIBUTES_ACCESSED": False
}
```

## `trackings` database

`dj_tracker` gives the possibility to have a separate table to store trackings. This can be useful if you intend to run it with your tests, to track model instances in different databases (`staging`, `production`, ...) but also to monitor your queries between releases.

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

### Run migrations

Run the migrations for the `trackings` database:

```shell
python manage.py migrate dj_tracker --database=trackings
```
