from sqlalchemy import inspect
from ...core.db import engine
from ..models.alert import Alert

if __name__ == "__main__":
    insp = inspect(engine)
    table_name = Alert.__tablename__
    exists = insp.has_table(table_name)
    if not exists:
        Alert.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "created", "table": table_name})
    else:
        # Ensure table exists (idempotent create)
        Alert.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "exists", "table": table_name})
