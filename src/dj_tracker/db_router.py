class DjTrackerRouter:
    app_label = "dj_tracker"
    db_alias = "trackings"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.app_label:
            return self.db_alias

    db_for_write = db_for_read

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == self.db_alias:
            return app_label == self.app_label
        if app_label == self.app_label:
            return False
