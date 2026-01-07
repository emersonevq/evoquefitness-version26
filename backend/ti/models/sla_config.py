from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, Float, Time, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from core.db import Base


class SLAConfiguration(Base):
    __tablename__ = "sla_configuration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prioridade: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    tempo_resposta_horas: Mapped[float] = mapped_column(Float, nullable=False)
    tempo_resolucao_horas: Mapped[float] = mapped_column(Float, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_reset_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SLABusinessHours(Base):
    __tablename__ = "sla_business_hours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dia_semana: Mapped[int] = mapped_column(Integer, nullable=False)
    hora_inicio: Mapped[str] = mapped_column(String(5), nullable=False)
    hora_fim: Mapped[str] = mapped_column(String(5), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SLAFeriado(Base):
    __tablename__ = "sla_feriados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HistoricoSLA(Base):
    __tablename__ = "historico_sla"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chamado_id: Mapped[int] = mapped_column(Integer, nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    status_anterior: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status_novo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_conclusao_anterior: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_conclusao_nova: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tempo_resposta_horas: Mapped[float | None] = mapped_column(Float, nullable=True)
    limite_sla_resposta_horas: Mapped[float | None] = mapped_column(Float, nullable=True)
    tempo_resolucao_horas: Mapped[float | None] = mapped_column(Float, nullable=True)
    limite_sla_horas: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_sla: Mapped[str | None] = mapped_column(String(50), nullable=True)
    criado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
