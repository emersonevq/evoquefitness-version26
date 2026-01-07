"""
Script para sincronizar todos os chamados existentes com a tabela de histórico de SLA.
Este script deve ser executado uma vez para popular a tabela de SLA com dados históricos.

Uso:
    python -m ti.scripts.sync_chamados_sla
"""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.db import SessionLocal, engine
from ti.models.chamado import Chamado
from ti.models.sla_config import HistoricoSLA, SLAConfiguration, SLABusinessHours
from ti.services.sla import SLACalculator
from core.utils import now_brazil_naive


def ensure_default_sla_config(db: Session) -> dict:
    """
    Garante que existem configurações de SLA padrão.
    Cria configurações padrão se não existirem.

    Retorna:
        dict: Estatísticas de criação
    """
    stats = {
        "tabelas_criadas": [],
        "configs_criadas": 0,
        "configs_existentes": 0,
        "horarios_criados": 0,
    }

    try:
        # Criar tabelas se não existirem
        SLAConfiguration.__table__.create(bind=engine, checkfirst=True)
        SLABusinessHours.__table__.create(bind=engine, checkfirst=True)
        HistoricoSLA.__table__.create(bind=engine, checkfirst=True)
        stats["tabelas_criadas"] = ["sla_configuration", "sla_business_hours", "historico_sla"]
    except Exception as e:
        print(f"⚠️  Aviso ao criar tabelas: {e}")

    try:
        # Verificar e criar configurações de SLA padrão
        default_configs = [
            ("Crítico", 1.0, 4.0, "Problemas críticos que afetam múltiplos usuários"),
            ("Alto", 2.0, 8.0, "Problemas de alta prioridade"),
            ("Normal", 4.0, 24.0, "Problemas normais"),
            ("Baixo", 8.0, 48.0, "Problemas de baixa prioridade"),
        ]

        for prioridade, tempo_resp, tempo_resol, desc in default_configs:
            existing = db.query(SLAConfiguration).filter(
                SLAConfiguration.prioridade == prioridade
            ).first()

            if existing:
                stats["configs_existentes"] += 1
            else:
                config = SLAConfiguration(
                    prioridade=prioridade,
                    tempo_resposta_horas=tempo_resp,
                    tempo_resolucao_horas=tempo_resol,
                    descricao=desc,
                    ativo=True,
                    criado_em=now_brazil_naive(),
                    atualizado_em=now_brazil_naive(),
                )
                db.add(config)
                stats["configs_criadas"] += 1

        db.commit()

        # Verificar e criar horários comerciais padrão (seg-sex 08:00-18:00)
        default_hours = [
            (0, "08:00", "18:00"),  # Segunda
            (1, "08:00", "18:00"),  # Terça
            (2, "08:00", "18:00"),  # Quarta
            (3, "08:00", "18:00"),  # Quinta
            (4, "08:00", "18:00"),  # Sexta
        ]

        for dia_semana, hora_inicio, hora_fim in default_hours:
            existing = db.query(SLABusinessHours).filter(
                SLABusinessHours.dia_semana == dia_semana
            ).first()

            if not existing:
                hours = SLABusinessHours(
                    dia_semana=dia_semana,
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    ativo=True,
                    criado_em=now_brazil_naive(),
                    atualizado_em=now_brazil_naive(),
                )
                db.add(hours)
                stats["horarios_criados"] += 1

        db.commit()

    except Exception as e:
        print(f"❌ Erro ao criar configurações padrão: {e}")
        db.rollback()
        raise

    return stats


def sync_chamados_to_sla(db: Session) -> dict:
    """
    Sincroniza todos os chamados com a tabela de histórico de SLA.

    Retorna:
        dict: Estatísticas da sincronização
    """
    stats = {
        "total_chamados": 0,
        "sincronizados": 0,
        "ja_sincronizados": 0,
        "sem_configuracao": 0,
        "erros": 0,
        "detalhes": [],
    }

    try:
        chamados = db.query(Chamado).all()
        stats["total_chamados"] = len(chamados)

        if stats["total_chamados"] == 0:
            print("ℹ️  Nenhum chamado encontrado para sincronizar.")
            return stats

        for chamado in chamados:
            try:
                # Verifica se já existe histórico para este chamado
                existing = db.query(HistoricoSLA).filter(
                    HistoricoSLA.chamado_id == chamado.id
                ).first()

                if existing:
                    stats["ja_sincronizados"] += 1
                    continue

                # Calcula o status de SLA atual
                sla_status = SLACalculator.get_sla_status(db, chamado)

                # Se não há configuração de SLA, registra e pula
                if sla_status.get("status_geral") == "sem_sla":
                    stats["sem_configuracao"] += 1
                    stats["detalhes"].append({
                        "chamado_id": chamado.id,
                        "codigo": chamado.codigo,
                        "status": "sem_configuracao",
                        "prioridade": chamado.prioridade,
                        "mensagem": f"Chamado {chamado.codigo} com prioridade '{chamado.prioridade}' não tem SLA configurada"
                    })
                    continue

                # Extrai métricas de resposta e resolução
                resposta_metric = sla_status.get("resposta_metric")
                resolucao_metric = sla_status.get("resolucao_metric")

                tempo_resposta_horas = resposta_metric.get("tempo_decorrido_horas") if resposta_metric else None
                limite_sla_resposta_horas = resposta_metric.get("tempo_limite_horas") if resposta_metric else None
                tempo_resolucao_horas = resolucao_metric.get("tempo_decorrido_horas") if resolucao_metric else None
                limite_sla_horas = resolucao_metric.get("tempo_limite_horas") if resolucao_metric else None

                # Cria o registro histórico inicial
                historico = HistoricoSLA(
                    chamado_id=chamado.id,
                    usuario_id=None,
                    acao="sincronizacao_inicial",
                    status_anterior=None,
                    status_novo=chamado.status,
                    tempo_resposta_horas=tempo_resposta_horas,
                    limite_sla_resposta_horas=limite_sla_resposta_horas,
                    tempo_resolucao_horas=tempo_resolucao_horas,
                    limite_sla_horas=limite_sla_horas,
                    status_sla=sla_status.get("status_geral"),
                    criado_em=chamado.data_abertura or now_brazil_naive(),
                )
                db.add(historico)
                db.commit()

                stats["sincronizados"] += 1
                stats["detalhes"].append({
                    "chamado_id": chamado.id,
                    "codigo": chamado.codigo,
                    "status": "sincronizado",
                    "prioridade": chamado.prioridade,
                    "tempo_resolucao": round(tempo_resolucao_horas or 0, 2),
                })

            except Exception as e:
                stats["erros"] += 1
                stats["detalhes"].append({
                    "chamado_id": chamado.id,
                    "codigo": getattr(chamado, "codigo", "?"),
                    "status": "erro",
                    "erro": str(e),
                })
                db.rollback()

        return stats

    except Exception as e:
        stats["erros"] += 1
        stats["detalhes"].append({
            "status": "erro_geral",
            "erro": str(e),
        })
        db.rollback()
        return stats


def main():
    """Executa a sincronização"""
    print("🔄 Iniciando sincronização de chamados com SLA...")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Etapa 1: Garantir configurações padrão
        print("\n📋 Etapa 1: Verificando e criando configurações de SLA padrão...")
        print("-" * 70)
        config_stats = ensure_default_sla_config(db)

        if config_stats["tabelas_criadas"]:
            print(f"   ✅ Tabelas criadas: {', '.join(config_stats['tabelas_criadas'])}")
        if config_stats["configs_criadas"] > 0:
            print(f"   ✅ Configurações de SLA criadas: {config_stats['configs_criadas']}")
        if config_stats["configs_existentes"] > 0:
            print(f"   ℹ️  Configurações de SLA já existentes: {config_stats['configs_existentes']}")
        if config_stats["horarios_criados"] > 0:
            print(f"   ✅ Horários comerciais criados: {config_stats['horarios_criados']}")

        # Etapa 2: Sincronizar chamados
        print("\n📊 Etapa 2: Sincronizando chamados com histórico de SLA...")
        print("-" * 70)
        stats = sync_chamados_to_sla(db)

        print(f"\n✅ Sincronização concluída!")
        print(f"   Total de chamados: {stats['total_chamados']}")
        print(f"   Sincronizados: {stats['sincronizados']}")
        print(f"   Já sincronizados: {stats['ja_sincronizados']}")
        print(f"   Sem configuração de SLA: {stats['sem_configuracao']}")
        print(f"   Erros: {stats['erros']}")
        print("=" * 70)

        if stats["detalhes"]:
            print("\n📋 Detalhes da sincronização (primeiros 15):")
            for detalhe in stats["detalhes"][:15]:
                cod = detalhe.get("codigo", detalhe.get("chamado_id", "?"))
                status = detalhe.get("status", "?")
                msg = detalhe.get("mensagem") or detalhe.get("erro") or detalhe.get("tempo_resolucao", "")
                print(f"   • [{cod}] {status}: {msg}")

    except Exception as e:
        print(f"\n❌ Erro fatal durante sincronização: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        print("\n✨ Finalizando...\n")


if __name__ == "__main__":
    main()
