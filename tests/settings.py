from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-2p1&(r-6(88=)txivii25r^o%4-&00u5vgs#n93r#t8+y0"

DEBUG = True

INSTALLED_APPS = [
    "dj_tracker",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "tests",
]

MIDDLEWARE = [
    "dj_tracker.middleware.DjTrackerMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    },
    "trackings": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "trackingsdb"),
    },
}

DATABASE_ROUTERS = ["dj_tracker.db_router.DjTrackerRouter"]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

STATIC_URL = "/static/"

ROOT_URLCONF = "dj_tracker.urls"

AUTH_USER_MODEL = "tests.User"

DJ_TRACKER = {
    "COLLECTION_INTERVAL": 1,
}

TEST_RUNNER = "dj_tracker.test.DjTrackerRunner"
