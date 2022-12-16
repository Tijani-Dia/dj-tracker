import sys

from django.apps import AppConfig


class DjTrackerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dj_tracker"

    def ready(self):
        from dj_tracker.constants import COMMANDS

        if "manage.py" in sys.argv[0] and sys.argv[1] in COMMANDS:
            from dj_tracker import tracker

            tracker.start()
