from django.apps import apps

from dj_tracker.cache_utils import cached_attribute


class DjTrackerRouter:
    app_label = "dj_tracker"
    db_alias = "trackings"

    @cached_attribute
    def models(cls):
        return frozenset(
            apps.get_app_config(cls.app_label).get_models(include_auto_created=True)
        )

    def db_for_read(self, model, **hints):
        if model in self.models:
            return self.db_alias

    db_for_write = db_for_read

    def allow_migrate(self, db, app_label, **hints):
        if app_label == self.app_label:
            return db == self.db_alias
        if db == self.db_alias:
            return False
