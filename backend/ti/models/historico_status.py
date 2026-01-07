from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.db import Base

class HistoricoStatus(Base):
    __tablename__ = "historico_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chamado_id: Mapped[int] = mapped_column(Integer, ForeignKey("chamado.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    data_inicio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Campos antigos compatibilidade (mapeamento virtual)
    @property
    def status_anterior(self) -> str | None:
        """Extrai status anterior da descrição"""
        if self.descricao and "→" in self.descricao:
            parts = self.descricao.split("→")
            if len(parts) > 0:
                return parts[0].replace("Migrado: ", "").strip()
        return None

    @property
    def status_novo(self) -> str | None:
        """Retorna o status atual (status)"""
        return self.status

    @property
    def data_acao(self) -> datetime | None:
        """Para compatibilidade: retorna data_inicio"""
        return self.data_inicio

    chamado: Mapped["Chamado"] = relationship("Chamado", back_populates="historicos_status")
