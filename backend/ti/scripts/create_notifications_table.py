from __future__ import annotations
from sqlalchemy import inspect
from ...core.db import engine
from ..models.notification import Notification


def main() -> None:
    insp = inspect(engine)
    table_name = Notification.__tablename__
    exists = insp.has_table(table_name)
    if not exists:
        Notification.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "created", "table": table_name})
    else:
        # Garantir colunas atualizadas (idempotente)
        Notification.__table__.create(bind=engine, checkfirst=True)
        print({"ok": True, "action": "exists", "table": table_name})


if __name__ == "__main__":
    main()
