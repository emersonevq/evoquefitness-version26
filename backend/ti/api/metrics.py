from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.db import get_db
from core.utils import now_brazil_naive
from ti.services.metrics import MetricsCalculator

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics/realtime")
def get_realtime_metrics(db: Session = Depends(get_db)):
    """
    Retorna métricas instantâneas (sem cache, sem cálculos pesados).

    Endpoint consolidado para dados rápidos:
    - chamados_hoje: Quantidade de chamados abertos hoje
    - comparacao_ontem: Comparação com ontem
    - abertos_agora: Quantidade de chamados ativos
    - timestamp: Momento do cálculo
    """
    try:
        return {
            "chamados_hoje": MetricsCalculator.get_chamados_abertos_hoje(db),
            "comparacao_ontem": MetricsCalculator.get_comparacao_ontem(db),
            "abertos_agora": MetricsCalculator.get_abertos_agora(db),
            "timestamp": now_brazil_naive().isoformat(),
        }
    except Exception as e:
        print(f"[ERROR] Erro ao calcular métricas em tempo real: {e}")
        import traceback
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao calcular métricas em tempo real: {str(e)}"
        )


@router.get("/metrics/dashboard/basic")
def get_basic_metrics(db: Session = Depends(get_db)):
    """
    [DEPRECATED] Use /metrics/realtime instead.

    Mantido por compatibilidade com código antigo.
    """
    return get_realtime_metrics(db)


@router.get("/metrics/dashboard/sla")
def get_sla_metrics(db: Session = Depends(get_db)):
    """
    Retorna métricas de SLA (carrega SEPARADO - mais lento, mas com cache).

    Retorna:
    - sla_compliance_24h: Percentual de SLA cumprido (ativos)
    - sla_compliance_mes: Percentual de SLA cumprido (todo o mês)
    - sla_distribution: Distribuição dentro/fora SLA (sincronizado com sla_compliance_mes)
    - tempo_resposta_24h: Tempo médio de primeira resposta 24h
    - tempo_resposta_mes: Tempo médio de primeira resposta mês
    - total_chamados_mes: Total de chamados deste mês
    """
    try:
        # Valida tipos esperados com exceções explícitas
        tempo_resposta_mes, total_chamados_mes = MetricsCalculator.get_tempo_medio_resposta_mes(db)
        if not isinstance(tempo_resposta_mes, str):
            raise TypeError(f"tempo_resposta_mes deve ser string, recebido: {type(tempo_resposta_mes)}")
        if not isinstance(total_chamados_mes, int):
            raise TypeError(f"total_chamados_mes deve ser int, recebido: {type(total_chamados_mes)}")

        tempo_resposta_24h = MetricsCalculator.get_tempo_medio_resposta_24h(db)
        if not isinstance(tempo_resposta_24h, str):
            raise TypeError(f"tempo_resposta_24h deve ser string, recebido: {type(tempo_resposta_24h)}")

        sla_distribution = MetricsCalculator.get_sla_distribution(db)
        if not isinstance(sla_distribution, dict):
            raise TypeError(f"sla_distribution deve ser dict, recebido: {type(sla_distribution)}")

        # Valida estrutura de sla_distribution
        required_keys = {"dentro_sla", "fora_sla", "percentual_dentro", "percentual_fora", "total"}
        if not required_keys.issubset(sla_distribution.keys()):
            raise ValueError(f"sla_distribution falta chaves: {required_keys - set(sla_distribution.keys())}")

        sla_24h = MetricsCalculator.get_sla_compliance_24h(db)
        if not isinstance(sla_24h, int):
            raise TypeError(f"sla_compliance_24h deve ser int, recebido: {type(sla_24h)}")
        if not (0 <= sla_24h <= 100):
            raise ValueError(f"sla_compliance_24h deve estar entre 0-100, recebido: {sla_24h}")

        sla_mes = MetricsCalculator.get_sla_compliance_mes(db)
        if not isinstance(sla_mes, int):
            raise TypeError(f"sla_compliance_mes deve ser int, recebido: {type(sla_mes)}")
        if not (0 <= sla_mes <= 100):
            raise ValueError(f"sla_compliance_mes deve estar entre 0-100, recebido: {sla_mes}")

        return {
            "sla_compliance_24h": sla_24h,
            "sla_compliance_mes": sla_mes,
            "sla_distribution": sla_distribution,
            "tempo_resposta_24h": tempo_resposta_24h,
            "tempo_resposta_mes": tempo_resposta_mes,
            "total_chamados_mes": total_chamados_mes,
        }
    except (TypeError, ValueError) as e:
        # Logging de erro explícito - não mascara
        print(f"[VALIDATION ERROR] Erro ao validar métricas SLA: {e}")
        import traceback
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Erro no cálculo de métricas SLA: {str(e)}"
        )
    except Exception as e:
        print(f"[ERROR] Erro inesperado ao calcular métricas SLA: {e}")
        import traceback
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao calcular métricas SLA: {str(e)}"
        )


@router.get("/metrics/dashboard")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Endpoint consolidado: Retorna TODAS as métricas do dashboard administrativo.

    Combina:
    - Métricas rápidas (realtime)
    - Métricas de SLA (com cache)
    - Métricas de performance

    Retorna:
    - chamados_hoje: Quantidade de chamados abertos hoje
    - comparacao_ontem: Comparação com ontem (hoje, ontem, percentual, direcao)
    - tempo_resposta_24h: Tempo médio de primeira resposta 24h
    - tempo_resposta_mes: Tempo médio de primeira resposta mês
    - total_chamados_mes: Total de chamados deste mês
    - sla_compliance_24h: Percentual de SLA cumprido (últimos chamados ativos)
    - sla_compliance_mes: Percentual de SLA cumprido (mês)
    - sla_distribution: Distribuição dentro/fora SLA
    - abertos_agora: Quantidade de chamados ativos
    - tempo_resolucao_30dias: Tempo médio de resolução (30 dias)
    - timestamp: Momento do cálculo
    """
    try:
        # Obtém todas as métricas
        realtime = get_realtime_metrics(db)
        sla = get_sla_metrics(db)
        performance = MetricsCalculator.get_performance_metrics(db)

        return {
            # Realtime
            "chamados_hoje": realtime["chamados_hoje"],
            "comparacao_ontem": realtime["comparacao_ontem"],
            "abertos_agora": realtime["abertos_agora"],

            # SLA
            "sla_compliance_24h": sla["sla_compliance_24h"],
            "sla_compliance_mes": sla["sla_compliance_mes"],
            "sla_distribution": sla["sla_distribution"],
            "tempo_resposta_24h": sla["tempo_resposta_24h"],
            "tempo_resposta_mes": sla["tempo_resposta_mes"],
            "total_chamados_mes": sla["total_chamados_mes"],

            # Performance
            "tempo_resolucao_30dias": performance["tempo_resolucao_medio"],
            "primeira_resposta_media": performance["primeira_resposta_media"],
            "taxa_reaberturas": performance["taxa_reaberturas"],
            "chamados_backlog": performance["chamados_backlog"],

            # Metadata
            "timestamp": now_brazil_naive().isoformat(),
        }
    except Exception as e:
        print(f"[ERROR] Erro ao calcular métricas do dashboard: {e}")
        import traceback
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao calcular métricas do dashboard: {str(e)}"
        )


@router.get("/metrics/chamados-abertos")
def get_chamados_abertos(db: Session = Depends(get_db)):
    """
    [DEPRECATED] Use /metrics/realtime instead.

    Retorna quantidade de chamados ativos (não concluídos nem cancelados)
    """
    try:
        count = MetricsCalculator.get_abertos_agora(db)
        return {"ativos": count}
    except Exception as e:
        print(f"Erro ao contar chamados ativos: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@router.get("/metrics/chamados-hoje")
def get_chamados_hoje(db: Session = Depends(get_db)):
    """
    [DEPRECATED] Use /metrics/realtime instead.

    Retorna quantidade de chamados abertos hoje
    """
    try:
        count = MetricsCalculator.get_chamados_abertos_hoje(db)
        return {"chamados_hoje": count}
    except Exception as e:
        print(f"Erro ao contar chamados de hoje: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@router.get("/metrics/tempo-resposta")
def get_tempo_resposta(db: Session = Depends(get_db)):
    """
    [DEPRECATED] Use /metrics/dashboard/sla instead.

    Retorna tempo médio de resposta das últimas 24h
    """
    try:
        tempo = MetricsCalculator.get_tempo_medio_resposta_24h(db)
        return {"tempo_resposta": tempo}
    except Exception as e:
        print(f"Erro ao calcular tempo de resposta: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@router.get("/metrics/sla-compliance")
def get_sla_compliance(db: Session = Depends(get_db)):
    """
    [DEPRECATED] Use /metrics/dashboard/sla instead.

    Retorna percentual de SLA cumprido nas últimas 24h
    """
    try:
        percentual = MetricsCalculator.get_sla_compliance_24h(db)
        return {"sla_compliance": percentual}
    except Exception as e:
        print(f"Erro ao calcular SLA compliance: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@router.get("/metrics/chamados-por-dia")
def get_chamados_por_dia(dias: int = 7, statuses: str = "", db: Session = Depends(get_db)):
    """Retorna quantidade de chamados por dia dos últimos N dias

    Query params:
    - dias: Número de dias (default: 7)
    - statuses: Lista separada por vírgula (ex: "Aberto,Em andamento")
    """
    try:
        status_list = [s.strip() for s in statuses.split(",") if s.strip()] if statuses else []
        dados = MetricsCalculator.get_chamados_por_dia(db, dias, status_list if status_list else None)
        if not isinstance(dados, list):
            return {"dados": []}
        return {"dados": dados}
    except Exception as e:
        print(f"Erro ao calcular chamados por dia: {e}")
        import traceback
        traceback.print_exc()
        return {"dados": []}


@router.get("/metrics/chamados-por-semana")
def get_chamados_por_semana(semanas: int = 4, statuses: str = "", db: Session = Depends(get_db)):
    """Retorna quantidade de chamados por semana dos últimos N semanas

    Query params:
    - semanas: Número de semanas (default: 4)
    - statuses: Lista separada por vírgula (ex: "Aberto,Em andamento")
    """
    try:
        status_list = [s.strip() for s in statuses.split(",") if s.strip()] if statuses else []
        dados = MetricsCalculator.get_chamados_por_semana(db, semanas, status_list if status_list else None)
        if not isinstance(dados, list):
            return {"dados": []}
        return {"dados": dados}
    except Exception as e:
        print(f"Erro ao calcular chamados por semana: {e}")
        import traceback
        traceback.print_exc()
        return {"dados": []}


@router.get("/metrics/chamados-por-mes")
def get_chamados_por_mes(range: str = "30d", statuses: str = "", db: Session = Depends(get_db)):
    """Retorna quantidade de chamados por status por mês

    Query params:
    - range: '7d', '30d', '90d' ou 'all' (padrão: '30d')
    - statuses: Lista separada por vírgula (ex: "Aberto,Em andamento,Concluído")
                Se vazio, mostra todos os status
    """
    try:
        meses_param = {
            "7d": 1,
            "30d": 3,
            "90d": 12,
            "all": 24
        }.get(range, 3)

        status_list = [s.strip() for s in statuses.split(",") if s.strip()] if statuses else []
        dados = MetricsCalculator.get_chamados_por_mes(db, meses_param, status_list if status_list else None)
        if not isinstance(dados, list):
            return {"dados": []}
        return {"dados": dados}
    except Exception as e:
        print(f"Erro ao calcular chamados por mês: {e}")
        import traceback
        traceback.print_exc()
        return {"dados": []}


@router.get("/metrics/sla-distribution")
def get_sla_distribution(db: Session = Depends(get_db)):
    """Retorna distribuição de SLA (dentro/fora do acordo)"""
    try:
        dist = MetricsCalculator.get_sla_distribution(db)

        # Valida tipo esperado com exceção explícita
        if not isinstance(dist, dict):
            raise TypeError(f"sla_distribution deve retornar dict, recebido: {type(dist)}")

        # Valida estrutura obrigatória
        required_keys = {"dentro_sla", "fora_sla", "percentual_dentro", "percentual_fora", "total"}
        missing_keys = required_keys - set(dist.keys())
        if missing_keys:
            raise ValueError(f"sla_distribution falta chaves obrigatórias: {missing_keys}")

        # Valida tipos de cada campo
        if not all(isinstance(dist[k], int) for k in required_keys):
            raise TypeError(f"Todos os campos de sla_distribution devem ser int")

        # Valida ranges
        if not (0 <= dist["percentual_dentro"] <= 100):
            raise ValueError(f"percentual_dentro deve estar entre 0-100")
        if not (0 <= dist["percentual_fora"] <= 100):
            raise ValueError(f"percentual_fora deve estar entre 0-100")

        return dist

    except (TypeError, ValueError) as e:
        print(f"[VALIDATION ERROR] Erro ao validar distribuição de SLA: {e}")
        import traceback
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao calcular distribuição de SLA: {str(e)}"
        )
    except Exception as e:
        print(f"[ERROR] Erro inesperado ao calcular distribuição de SLA: {e}")
        import traceback
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao calcular distribuição de SLA: {str(e)}"
        )


@router.get("/metrics/performance")
def get_performance_metrics(db: Session = Depends(get_db)):
    """Retorna métricas de performance (últimos 30 dias)"""
    try:
        metricas = MetricsCalculator.get_performance_metrics(db)
        return metricas
    except Exception as e:
        print(f"Erro ao calcular métricas de performance: {e}")
        return {
            "tempo_resolucao_medio": "—",
            "primeira_resposta_media": "—",
            "taxa_reaberturas": "0%",
            "chamados_backlog": 0
        }


@router.get("/metrics/debug/tempo-resposta")
def debug_tempo_resposta(periodo: str = "mes", db: Session = Depends(get_db)):
    """
    Debug: retorna dados brutos de tempo de resposta
    periodo: "mes", "24h" ou "30dias"
    """
    try:
        historicos = MetricsCalculator.debug_tempo_resposta(db, periodo)
        return {
            "status": "ok",
            "total_registros": len(historicos),
            "periodo": periodo
        }
    except Exception as e:
        print(f"Erro ao debugar tempo de resposta: {e}")
        return {
            "status": "erro",
            "erro": str(e),
            "periodo": periodo
        }


@router.post("/metrics/debug/recalculate-sla")
def debug_recalculate_sla(db: Session = Depends(get_db)):
    """
    Debug: força recálculo de todas as métricas de SLA
    Útil para verificar se há problemas nos cálculos
    """
    try:
        from ti.services.sla_cache import SLACacheManager
        from core.utils import now_brazil_naive

        # Invalida todos os caches
        SLACacheManager.invalidate_all_sla(db)

        # Recalcula
        sla_24h = MetricsCalculator.get_sla_compliance_24h(db)
        sla_mes = MetricsCalculator.get_sla_compliance_mes(db)
        sla_dist = MetricsCalculator.get_sla_distribution(db)

        return {
            "status": "ok",
            "sla_compliance_24h": sla_24h,
            "sla_compliance_mes": sla_mes,
            "sla_distribution": sla_dist,
            "timestamp": now_brazil_naive().isoformat()
        }
    except Exception as e:
        print(f"Erro ao recalcular SLA: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "erro",
            "erro": str(e)
        }


@router.get("/metrics/health")
def metrics_health_check(db: Session = Depends(get_db)):
    """
    Endpoint de health check para monitorar saúde do cache e cálculos.

    Retorna:
    - cache_status: Se cache está funcionando
    - cache_age: Idade do cache em segundos
    - debouncer_status: Quantas operações estão em progresso
    - banco_status: Se conexão com banco está OK
    - timestamp: Momento do check
    """
    try:
        from ti.services.cache_manager_incremental import IncrementalMetricsCache
        from ti.services.cache_debouncer import get_debouncer
        from core.utils import now_brazil_naive
        import json

        health = {
            "status": "healthy",
            "checks": {}
        }

        # Check 1: Cache accessibility
        try:
            from ti.models.metrics_cache import MetricsCacheDB
            cache_key = IncrementalMetricsCache.get_cache_key_month()
            cached = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key
            ).first()
            health["checks"]["cache"] = {
                "status": "ok",
                "message": "Cache accessible"
            }
        except Exception as cache_error:
            health["checks"]["cache"] = {
                "status": "warning",
                "message": str(cache_error)
            }

        # Check 2: Database connection
        try:
            db.execute("SELECT 1")
            health["checks"]["database"] = {
                "status": "ok",
                "message": "Database connected"
            }
        except Exception as db_error:
            health["checks"]["database"] = {
                "status": "critical",
                "message": str(db_error)
            }
            health["status"] = "unhealthy"

        # Check 3: Debouncer status
        try:
            debouncer = get_debouncer()
            stats = debouncer.get_stats()
            health["checks"]["debouncer"] = {
                "status": "ok",
                "cached_items": stats["cached_keys"],
                "in_progress": stats["in_progress"]
            }
        except Exception as debounce_error:
            health["checks"]["debouncer"] = {
                "status": "warning",
                "message": str(debounce_error)
            }

        # Check 4: Metrics calculation (lightweight)
        try:
            metricas = IncrementalMetricsCache.get_metrics(db)
            health["checks"]["metrics"] = {
                "status": "ok",
                "total_chamados": metricas.get("total", 0),
                "percentual_sla": metricas.get("percentual_dentro", 0)
            }
        except Exception as metrics_error:
            health["checks"]["metrics"] = {
                "status": "warning",
                "message": str(metrics_error)
            }

        health["timestamp"] = now_brazil_naive().isoformat()
        return health

    except Exception as e:
        print(f"Erro ao fazer health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": now_brazil_naive().isoformat()
        }
