from sqlalchemy import inspect
from ...core.db import engine
from ..models.media import Media


def main() -> None:
    insp = inspect(engine)
    table_name = Media.__tablename__
    exists = insp.has_table(table_name)
    if not exists:
        Media.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "created", "table": table_name})
    else:
        # Ensure table exists (idempotent create)
        Media.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "exists", "table": table_name})


if __name__ == "__main__":
    main()
