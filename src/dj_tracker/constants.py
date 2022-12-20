"""
The constants defined here are set dynamically on first access. For example,

```
from dj_tracker.constants import COMMANDS
```

will result in calling `_get_commands` on first access and set the value in this module's __dict__.

This is achieved through the `__getattr__` hook. See PEP 562 for more details.
"""

DJ_TRACKER_SETTINGS = None


def __getattr__(name):
    if getter := globals().pop(f"_get_{name.lower()}", None):
        globals()[name] = value = getter()
        return value

    raise AttributeError


def _set_dj_tracker_settings():
    global DJ_TRACKER_SETTINGS

    if DJ_TRACKER_SETTINGS is not None:
        return

    from django.conf import settings

    DJ_TRACKER_SETTINGS = {
        "COLLECTION_INTERVAL": 3,
        "FIELD_DESCRIPTORS": {},
        "APPS_TO_EXCLUDE": None,
        "IGNORE_MODULES": None,
        "IGNORE_PATHS": None,
    }
    DJ_TRACKER_SETTINGS.update(getattr(settings, "DJ_TRACKER", {}))


def _get_tracked_models():
    import itertools

    from django.apps import apps

    _set_dj_tracker_settings()

    apps_to_exclude = {"dj_tracker", "sessions"}
    if extra_apps_to_exclude := DJ_TRACKER_SETTINGS.pop("APPS_TO_EXCLUDE"):
        apps_to_exclude.update(set(extra_apps_to_exclude))

    return frozenset(
        itertools.chain.from_iterable(
            app.get_models()
            for app in apps.get_app_configs()
            if app.label not in apps_to_exclude
        )
    )


def _get_ignored_modules():
    _set_dj_tracker_settings()

    ignored_modules = {
        "wsgiref",
        "unittest",
        "threading",
        "socketserver",
        "dj_tracker",
        "django/db",
        "django/template",
        "django/test/",
        "django/core/servers",
        "django/core/handlers",
        "django/core/management",
        "django/contrib/staticfiles",
        "django/utils/deprecation.py",
        "manage.py",
    }
    if extra_ignored_modules := DJ_TRACKER_SETTINGS.pop("IGNORE_MODULES"):
        ignored_modules.update(set(extra_ignored_modules))

    return ignored_modules


def _get_ignored_paths():
    _set_dj_tracker_settings()

    ignored_paths = {"/dj-tracker/"}
    if extra_ignored_paths := DJ_TRACKER_SETTINGS.pop("IGNORE_PATHS"):
        ignored_paths.update(set(extra_ignored_paths))

    return ignored_paths


def _get_extra_descriptors():
    from django.utils.module_loading import import_string

    _set_dj_tracker_settings()
    return {
        name: import_string(path)
        for name, path in DJ_TRACKER_SETTINGS.pop("FIELD_DESCRIPTORS").items()
    }


def _get_collection_interval():
    _set_dj_tracker_settings()
    return DJ_TRACKER_SETTINGS.pop("COLLECTION_INTERVAL")


def _get_namespace():
    import uuid

    return uuid.UUID("7bdba457-2ced-4d0f-82b6-48c1b12f138c")


def _get_stopping():
    import threading

    return threading.Event()


def _get_dummy_request():
    class DummyRequest:
        path = ""
        method = ""
        content_type = ""
        META = {}

    return DummyRequest
