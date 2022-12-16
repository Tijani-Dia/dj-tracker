class DjTrackerRouter:
    app_label = "dj_tracker"
    db_alias = "trackings"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.app_label:
            return self.db_alias
        return None

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label == self.app_label:
            return obj2._meta.app_label == self.app_label
        elif obj2._meta.app_label == self.app_label:
            return obj1._meta.app_label == self.app_label
        else:
            return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == self.db_alias:
            return app_label == self.app_label
        return None
