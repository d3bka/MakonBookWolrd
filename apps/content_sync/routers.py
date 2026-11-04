"""Keep Django away from makonbook-api's database.

The ``makonbook_api`` alias is only ever read with raw SQL by
apps.content_sync.source. No model lives there and nothing is migrated there:
that schema belongs to makonbook-api (goose migrations).
"""

ALIAS = "makonbook_api"


class MakonbookApiRouter:
    def db_for_read(self, model, **hints):
        return None

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == ALIAS:
            return False
        return None
