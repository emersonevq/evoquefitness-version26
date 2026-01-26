from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.db import Base

class HistoricoStatus(Base):
    __tablename__ = "historico_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chamado_id: Mapped[int] = mapped_column(Integer, ForeignKey("chamado.id"), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    status_anterior: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status_novo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_inicio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def data_acao(self) -> datetime | None:
        """Para compatibilidade: retorna data_inicio"""
        return self.data_inicio

    chamado: Mapped["Chamado"] = relationship("Chamado", back_populates="historicos_status")
