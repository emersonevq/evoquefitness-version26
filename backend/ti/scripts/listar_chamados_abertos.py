from __future__ import annotations
from sqlalchemy import select
from ...core.db import SessionLocal
from ..models import Chamado


def main() -> None:
    with SessionLocal() as db:
        abertos = db.execute(select(Chamado).where(Chamado.status == "Aberto")).scalars().all()
        print(f"Chamados abertos: {len(abertos)}")
        for c in abertos[:20]:
            print(c.id, c.protocolo, c.solicitante, c.problema, c.unidade)

if __name__ == "__main__":
    main()
