import os

SECRET_KEY = "django-insecure-7ym(q98o+8ut^_9_ob$7xevnq1%u6bqasmke2kv!acl785n-q&"

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "app",
    "dj_tracker",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(os.getcwd(), "db.sqlite3"),
    },
    "trackings": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(os.getcwd(), "trackingsdb"),
    },
}

DATABASE_ROUTERS = ["dj_tracker.db_router.DjTrackerRouter"]

MIDDLEWARE = [
    # Remove the `dj-tracker` middleware when testing the `/time/` or `/memory/` endpoints.
    "dj_tracker.middleware.DjTrackerMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "wsgi.application"

ROOT_URLCONF = "urls"

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
