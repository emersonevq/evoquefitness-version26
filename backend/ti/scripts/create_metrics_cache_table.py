from sqlalchemy import inspect
from core.db import engine
from ti.models.metrics_cache import MetricsCacheDB


def create_metrics_cache_table():
    insp = inspect(engine)
    table_name = MetricsCacheDB.__tablename__
    exists = insp.has_table(table_name)
    if not exists:
        MetricsCacheDB.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "created", "table": table_name})
    else:
        MetricsCacheDB.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "exists", "table": table_name})


if __name__ == "__main__":
    create_metrics_cache_table()
