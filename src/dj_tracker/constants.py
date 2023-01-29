"""
The constants defined here are set on first access, dynamically. For example:
```
from dj_tracker.constants import TRACKED_MODELS
```
will result in calling `_get_tracked_models` on first access and set the value in this module's globals.

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
        "TRACK_ATTRIBUTES_ACCESSED": True,
        "COLLECTION_INTERVAL": 5,
        "FIELD_DESCRIPTORS": {},
        "APPS_TO_EXCLUDE": (),
        "IGNORE_MODULES": (),
        "IGNORE_PATHS": (),
    }
    DJ_TRACKER_SETTINGS.update(getattr(settings, "DJ_TRACKER", {}))


def _get_tracked_models():
    from itertools import chain

    from django.apps import apps

    _set_dj_tracker_settings()
    apps_to_exclude = {"dj_tracker", *DJ_TRACKER_SETTINGS.pop("APPS_TO_EXCLUDE")}
    return frozenset(
        chain.from_iterable(
            app.get_models(include_auto_created=True)
            for app in apps.get_app_configs()
            if app.label not in apps_to_exclude
        )
    )


def _get_ignored_modules():
    _set_dj_tracker_settings()
    return {
        "wsgiref",
        "gunicorn",
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
        *DJ_TRACKER_SETTINGS.pop("IGNORE_MODULES"),
    }


def _get_ignored_paths():
    _set_dj_tracker_settings()
    return {"/dj-tracker/", *DJ_TRACKER_SETTINGS.pop("IGNORE_PATHS")}


def _get_extra_descriptors():
    from django.utils.module_loading import import_string

    _set_dj_tracker_settings()
    return {
        name: import_string(path)
        for name, path in DJ_TRACKER_SETTINGS.pop("FIELD_DESCRIPTORS").items()
    }


def _get_track_attributes_accessed():
    _set_dj_tracker_settings()
    return DJ_TRACKER_SETTINGS.pop("TRACK_ATTRIBUTES_ACCESSED")


def _get_collection_interval():
    _set_dj_tracker_settings()
    return DJ_TRACKER_SETTINGS.pop("COLLECTION_INTERVAL")


def _get_trackings_db():
    from django.conf import settings

    return "trackings" if "trackings" in settings.DATABASES else "default"


def _get_dummy_request():
    return type("DummyRequest", (), {"path": "", "_ignore_path": False})
