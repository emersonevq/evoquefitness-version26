"""
Helper para garantir que todas as tabelas de SLA existem.
Chamado apenas uma vez na startup, não em cada endpoint.
"""

from core.db import engine
from ti.models.sla_config import SLAConfiguration, SLABusinessHours, SLAFeriado, HistoricoSLA


def ensure_sla_tables():
    """Cria todas as tabelas de SLA se não existirem"""
    try:
        SLAConfiguration.__table__.create(bind=engine, checkfirst=True)
        SLABusinessHours.__table__.create(bind=engine, checkfirst=True)
        SLAFeriado.__table__.create(bind=engine, checkfirst=True)
        HistoricoSLA.__table__.create(bind=engine, checkfirst=True)
        print("✅ Tabelas de SLA criadas com sucesso")
    except Exception as e:
        print(f"⚠️  Erro ao criar tabelas de SLA: {e}")
        raise
