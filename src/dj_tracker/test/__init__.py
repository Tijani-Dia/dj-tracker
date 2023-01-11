from django.core.management import call_command
from django.test.runner import DiscoverRunner

from dj_tracker import tracker


class DjTrackerRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        res = super().setup_databases(**kwargs)
        call_command(
            "migrate", database="trackings", app_label="dj_tracker", verbosity=0
        )
        return res

    def run_suite(self, suite, **kwargs):
        tracker.start()
        try:
            return super().run_suite(suite, **kwargs)
        finally:
            tracker.stop()
