from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from core.db import get_db, engine
from ti.schemas.sla import (
    SLAConfigurationCreate,
    SLAConfigurationUpdate,
    SLAConfigurationOut,
    SLABusinessHoursCreate,
    SLABusinessHoursOut,
    SLAFeriadoCreate,
    SLAFeriadoUpdate,
    SLAFeriadoOut,
    HistoricoSLAOut,
    SLAStatusResponse,
)
from ti.models.sla_config import SLAConfiguration, SLABusinessHours, SLAFeriado, HistoricoSLA
from ti.models.chamado import Chamado
from ti.services.sla import SLACalculator
from ti.services.sla_cache import SLACacheManager
from ti.services.sla_validator import SLAValidator
from core.utils import now_brazil_naive
from core.realtime import sio
from datetime import timedelta

router = APIRouter(prefix="/sla", tags=["TI - SLA"])


@router.get("/config", response_model=list[SLAConfigurationOut])
def listar_sla_config(db: Session = Depends(get_db)):
    try:
        return db.query(SLAConfiguration).order_by(SLAConfiguration.prioridade.asc()).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar configurações de SLA: {e}")


@router.post("/config", response_model=SLAConfigurationOut)
def criar_sla_config(payload: SLAConfigurationCreate, db: Session = Depends(get_db)):
    from ti.services.sla_transaction_manager import SLATransactionManager

    try:
        existente = db.query(SLAConfiguration).filter(
            SLAConfiguration.prioridade == payload.prioridade
        ).first()
        if existente:
            raise HTTPException(
                status_code=400,
                detail=f"Configuração de SLA para prioridade '{payload.prioridade}' já existe"
            )

        def _create_config(db_session: Session) -> dict:
            config = SLAConfiguration(
                prioridade=payload.prioridade,
                tempo_resposta_horas=payload.tempo_resposta_horas,
                tempo_resolucao_horas=payload.tempo_resolucao_horas,
                descricao=payload.descricao,
                ativo=payload.ativo,
                criado_em=now_brazil_naive(),
                atualizado_em=now_brazil_naive(),
            )
            db_session.add(config)
            db_session.flush()
            SLACacheManager.invalidate_all_sla(db_session)
            return config

        result = SLATransactionManager.execute_atomic(db, _create_config)

        if result.success:
            config = result.data
            db.refresh(config)
            return config
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar configuração de SLA: {e}")


@router.patch("/config/{config_id}", response_model=SLAConfigurationOut)
def atualizar_sla_config(
    config_id: int,
    payload: SLAConfigurationUpdate,
    db: Session = Depends(get_db)
):
    from ti.services.sla_transaction_manager import SLATransactionManager

    try:
        def _update_config(db_session: Session, config_id: int, payload: SLAConfigurationUpdate) -> SLAConfiguration:
            config = db_session.query(SLAConfiguration).filter(SLAConfiguration.id == config_id).first()
            if not config:
                raise HTTPException(status_code=404, detail="Configuração de SLA não encontrada")

            if payload.tempo_resposta_horas is not None:
                config.tempo_resposta_horas = payload.tempo_resposta_horas
            if payload.tempo_resolucao_horas is not None:
                config.tempo_resolucao_horas = payload.tempo_resolucao_horas
            if payload.descricao is not None:
                config.descricao = payload.descricao
            if payload.ativo is not None:
                config.ativo = payload.ativo

            config.atualizado_em = now_brazil_naive()
            db_session.add(config)
            db_session.flush()
            SLACacheManager.invalidate_all_sla(db_session)
            return config

        result = SLATransactionManager.execute_atomic(
            db, _update_config, config_id, payload
        )

        if result.success:
            config = result.data
            db.refresh(config)
            return config
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar configuração de SLA: {e}")


@router.delete("/config/{config_id}")
def deletar_sla_config(config_id: int, db: Session = Depends(get_db)):
    try:
        config = db.query(SLAConfiguration).filter(SLAConfiguration.id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="Configuração de SLA não encontrada")

        db.delete(config)
        db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar configuração de SLA: {e}")


@router.get("/business-hours", response_model=list[SLABusinessHoursOut])
def listar_business_hours(db: Session = Depends(get_db)):
    try:
        return db.query(SLABusinessHours).order_by(SLABusinessHours.dia_semana.asc()).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar horários comerciais: {e}")


@router.post("/business-hours", response_model=SLABusinessHoursOut)
def criar_business_hours(payload: SLABusinessHoursCreate, db: Session = Depends(get_db)):
    try:
        existente = db.query(SLABusinessHours).filter(
            SLABusinessHours.dia_semana == payload.dia_semana
        ).first()
        if existente:
            raise HTTPException(
                status_code=400,
                detail=f"Horário comercial para dia {payload.dia_semana} já existe"
            )

        bh = SLABusinessHours(
            dia_semana=payload.dia_semana,
            hora_inicio=payload.hora_inicio,
            hora_fim=payload.hora_fim,
            ativo=payload.ativo,
            criado_em=now_brazil_naive(),
            atualizado_em=now_brazil_naive(),
        )
        db.add(bh)
        db.commit()
        db.refresh(bh)
        return bh
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar horário comercial: {e}")


@router.patch("/business-hours/{bh_id}", response_model=SLABusinessHoursOut)
def atualizar_business_hours(
    bh_id: int,
    payload: SLABusinessHoursCreate,
    db: Session = Depends(get_db)
):
    try:
        bh = db.query(SLABusinessHours).filter(SLABusinessHours.id == bh_id).first()
        if not bh:
            raise HTTPException(status_code=404, detail="Horário comercial não encontrado")

        bh.hora_inicio = payload.hora_inicio
        bh.hora_fim = payload.hora_fim
        bh.ativo = payload.ativo
        bh.atualizado_em = now_brazil_naive()

        db.add(bh)
        db.commit()
        db.refresh(bh)
        return bh
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar horário comercial: {e}")


@router.delete("/business-hours/{bh_id}")
def deletar_business_hours(bh_id: int, db: Session = Depends(get_db)):
    try:
        bh = db.query(SLABusinessHours).filter(SLABusinessHours.id == bh_id).first()
        if not bh:
            raise HTTPException(status_code=404, detail="Horário comercial não encontrado")

        db.delete(bh)
        db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar horário comercial: {e}")


@router.get("/chamado/{chamado_id}/status", response_model=dict)
def obter_sla_status_chamado(chamado_id: int, db: Session = Depends(get_db)):
    try:
        chamado = db.query(Chamado).filter(
            (Chamado.id == chamado_id) & (Chamado.deletado_em.is_(None))
        ).first()
        if not chamado:
            raise HTTPException(status_code=404, detail="Chamado não encontrado")

        sla_status = SLACalculator.get_sla_status(db, chamado)
        return sla_status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter status de SLA: {e}")


@router.get("/historico/{chamado_id}", response_model=list[HistoricoSLAOut])
def obter_historico_sla(chamado_id: int, db: Session = Depends(get_db)):
    try:
        historicos = db.query(HistoricoSLA).filter(
            HistoricoSLA.chamado_id == chamado_id
        ).order_by(HistoricoSLA.criado_em.desc()).all()

        return historicos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter histórico de SLA: {e}")


@router.post("/sync/todos-chamados")
def sincronizar_todos_chamados(db: Session = Depends(get_db)):
    """
    Sincroniza todos os chamados existentes com a tabela de histórico de SLA.
    Operação atômica: ou sincroniza tudo ou não sincroniza nada.
    """
    from ti.services.sla_transaction_manager import SLATransactionManager

    try:
        def _sincronizar_impl(db_session: Session) -> dict:
            """Implementação da sincronização"""
            stats = {
                "total_chamados": 0,
                "sincronizados": 0,
                "atualizados": 0,
                "erros": 0,
            }

            chamados = db_session.query(Chamado).all()
            stats["total_chamados"] = len(chamados)

            for chamado in chamados:
                existing = db_session.query(HistoricoSLA).filter(
                    HistoricoSLA.chamado_id == chamado.id
                ).first()

                sla_status = SLACalculator.get_sla_status(db_session, chamado)

                resposta_metric = sla_status.get("resposta_metric")
                resolucao_metric = sla_status.get("resolucao_metric")

                tempo_resposta_horas = resposta_metric.get("tempo_decorrido_horas") if resposta_metric else None
                limite_sla_resposta_horas = resposta_metric.get("tempo_limite_horas") if resposta_metric else None
                tempo_resolucao_horas = resolucao_metric.get("tempo_decorrido_horas") if resolucao_metric else None
                limite_sla_horas = resolucao_metric.get("tempo_limite_horas") if resolucao_metric else None

                if existing:
                    existing.status_novo = chamado.status
                    existing.tempo_resposta_horas = tempo_resposta_horas
                    existing.limite_sla_resposta_horas = limite_sla_resposta_horas
                    existing.tempo_resolucao_horas = tempo_resolucao_horas
                    existing.limite_sla_horas = limite_sla_horas
                    existing.status_sla = sla_status.get("status_geral")
                    db_session.add(existing)
                    stats["atualizados"] += 1
                else:
                    historico = HistoricoSLA(
                        chamado_id=chamado.id,
                        usuario_id=None,
                        acao="sincronizacao",
                        status_anterior=None,
                        status_novo=chamado.status,
                        tempo_resposta_horas=tempo_resposta_horas,
                        limite_sla_resposta_horas=limite_sla_resposta_horas,
                        tempo_resolucao_horas=tempo_resolucao_horas,
                        limite_sla_horas=limite_sla_horas,
                        status_sla=sla_status.get("status_geral"),
                        criado_em=chamado.data_abertura or now_brazil_naive(),
                    )
                    db_session.add(historico)
                    stats["sincronizados"] += 1

            return stats

        result = SLATransactionManager.execute_with_lock(
            db,
            "historico_sla",
            _sincronizar_impl
        )

        if result.success:
            return result.data
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar chamados: {e}")


@router.post("/recalcular/painel")
def recalcular_sla_painel(db: Session = Depends(get_db)):
    """
    Recalcula todos os SLAs quando o painel administrativo é acessado.
    Operação atômica: ou recalcula tudo ou não recalcula nada.
    """
    from ti.services.sla_transaction_manager import SLATransactionManager

    try:
        def _recalcular_impl(db_session: Session) -> dict:
            """Implementação do recálculo"""
            stats = {
                "total_recalculados": 0,
                "em_dia": 0,
                "vencidos": 0,
                "em_andamento": 0,
                "congelados": 0,
                "erros": 0,
            }

            chamados = db_session.query(Chamado).filter(
                and_(
                    Chamado.status != "Cancelado",
                    Chamado.status != "Concluído"
                )
            ).all()

            for chamado in chamados:
                sla_status = SLACalculator.get_sla_status(db_session, chamado)

                resposta_metric = sla_status.get("resposta_metric")
                resolucao_metric = sla_status.get("resolucao_metric")

                tempo_resposta_horas = resposta_metric.get("tempo_decorrido_horas") if resposta_metric else None
                limite_sla_resposta_horas = resposta_metric.get("tempo_limite_horas") if resposta_metric else None
                tempo_resolucao_horas = resolucao_metric.get("tempo_decorrido_horas") if resolucao_metric else None
                limite_sla_horas = resolucao_metric.get("tempo_limite_horas") if resolucao_metric else None

                existing = db_session.query(HistoricoSLA).filter(
                    HistoricoSLA.chamado_id == chamado.id
                ).order_by(HistoricoSLA.criado_em.desc()).first()

                if existing:
                    existing.tempo_resposta_horas = tempo_resposta_horas
                    existing.limite_sla_resposta_horas = limite_sla_resposta_horas
                    existing.tempo_resolucao_horas = tempo_resolucao_horas
                    existing.limite_sla_horas = limite_sla_horas
                    existing.status_sla = sla_status.get("status_geral")
                    db_session.add(existing)
                else:
                    historico = HistoricoSLA(
                        chamado_id=chamado.id,
                        usuario_id=None,
                        acao="recalculo_painel",
                        status_novo=chamado.status,
                        tempo_resposta_horas=tempo_resposta_horas,
                        limite_sla_resposta_horas=limite_sla_resposta_horas,
                        tempo_resolucao_horas=tempo_resolucao_horas,
                        limite_sla_horas=limite_sla_horas,
                        status_sla=sla_status.get("status_geral"),
                        criado_em=now_brazil_naive(),
                    )
                    db_session.add(historico)

                stats["total_recalculados"] += 1

                status_sla = sla_status.get("status_geral", "sem_sla")
                if status_sla in ["cumprido", "dentro_prazo"]:
                    stats["em_dia"] += 1
                elif status_sla in ["violado", "vencido_ativo"]:
                    stats["vencidos"] += 1
                elif status_sla == "proximo_vencer":
                    stats["em_andamento"] += 1
                elif status_sla == "pausado":
                    stats["congelados"] += 1

            return stats

        result = SLATransactionManager.execute_with_lock(
            db,
            "historico_sla",
            _recalcular_impl
        )

        if result.success:
            print(f"[PAINEL RECALC] Invalidando cache de métricas...")
            try:
                from ti.services.cache_manager_incremental import IncrementalMetricsCache
                IncrementalMetricsCache.invalidate_all()
            except Exception as e:
                print(f"[PAINEL RECALC] Aviso ao invalidar cache: {e}")

            try:
                import anyio
                stats = result.data
                anyio.from_thread.run(sio.emit, "metrics:updated", {
                    "total_recalculados": stats.get("total_recalculados"),
                    "em_dia": stats.get("em_dia"),
                    "vencidos": stats.get("vencidos"),
                    "em_andamento": stats.get("em_andamento"),
                    "congelados": stats.get("congelados"),
                    "timestamp": now_brazil_naive().isoformat(),
                })
                print(f"[PAINEL RECALC] ✅ Evento WebSocket emitido para frontend")
            except Exception as e:
                print(f"[PAINEL RECALC] ⚠️  Erro ao emitir evento WebSocket: {e}")

            return result.data
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao recalcular SLAs: {e}")


@router.post("/cache/invalidate-chamado/{chamado_id}")
def invalidar_cache_chamado(chamado_id: int, db: Session = Depends(get_db)):
    """Invalida caches relacionados a um chamado específico."""
    try:
        SLACacheManager.invalidate_by_chamado(db, chamado_id)
        return {"ok": True, "chamado_id": chamado_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao invalidar cache: {e}")


@router.post("/cache/invalidate-all")
def invalidar_todos_caches(db: Session = Depends(get_db)):
    """Invalida TODOS os caches de SLA."""
    try:
        SLACacheManager.invalidate_all_sla(db)
        return {"ok": True, "message": "Todos os caches de SLA foram invalidados"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao invalidar cache: {e}")


@router.post("/cache/warmup")
def preaquecer_cache(db: Session = Depends(get_db)):
    """Pré-aquece o cache ao abrir o painel administrativo."""
    try:
        from ti.services.metrics import MetricsCalculator
        import time

        stats = {
            "total_calculados": 0,
            "tempo_ms": 0,
            "erro": None
        }

        start = time.time()

        MetricsCalculator.get_sla_compliance_24h(db)
        MetricsCalculator.get_sla_compliance_mes(db)
        MetricsCalculator.get_sla_distribution(db)
        MetricsCalculator.get_tempo_medio_resposta_24h(db)
        MetricsCalculator.get_tempo_medio_resposta_mes(db)
        MetricsCalculator.get_abertos_agora(db)
        MetricsCalculator.get_chamados_abertos_hoje(db)

        stats["total_calculados"] = 7
        stats["tempo_ms"] = int((time.time() - start) * 1000)

        return stats
    except Exception as e:
        print(f"Erro ao preaquecer cache: {e}")
        import traceback
        traceback.print_exc()
        return {
            "total_calculados": 0,
            "tempo_ms": 0,
            "erro": str(e)
        }


@router.get("/cache/stats")
def obter_stats_cache(db: Session = Depends(get_db)):
    """Retorna estatísticas do sistema de cache."""
    try:
        stats = SLACacheManager.get_stats(db)
        return stats
    except Exception as e:
        return {
            "error": str(e),
            "memory_entries": 0,
            "database_entries": 0,
            "expired_in_db": 0
        }


@router.post("/cache/cleanup")
def limpar_cache_expirado(db: Session = Depends(get_db)):
    """Remove caches expirados do banco de dados."""
    try:
        removed = SLACacheManager.clear_expired(db)
        return {
            "ok": True,
            "removed": removed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao limpar cache: {e}")


@router.post("/cache/reset-all")
def resetar_todo_cache(db: Session = Depends(get_db)):
    """Reseta COMPLETAMENTE o cache de métricas e SLA."""
    try:
        from ti.models.metrics_cache import MetricsCacheDB

        db.query(MetricsCacheDB).delete()
        db.commit()

        SLACacheManager.invalidate_all_sla(db)

        return {
            "ok": True,
            "message": "Cache de métricas e SLA foi completamente resetado"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao resetar cache: {e}")


@router.post("/reset-and-recalculate")
def resetar_sla_completo(db: Session = Depends(get_db)):
    """
    Reseta COMPLETAMENTE o SLA:
    1. Limpa todo o cache de métricas (memória + banco)
    2. Registra a data de reset em cada configuração de SLA
    3. Remove dados de cache P90 incremental
    4. Próximos cálculos ignorarão dados anteriores ao reset
    """
    try:
        from ti.models.metrics_cache import MetricsCacheDB

        agora = now_brazil_naive()

        print(f"\n[SLA RESET] Iniciando reset completo do sistema SLA")

        print(f"[SLA RESET] Invalidando cache em memória...")
        SLACacheManager.invalidate_all_sla(db)

        print(f"[SLA RESET] Limpando banco de dados...")
        db.query(MetricsCacheDB).delete()

        print(f"[SLA RESET] Registrando data de reset nas configurações...")
        configs = db.query(SLAConfiguration).all()
        for config in configs:
            config.ultimo_reset_em = agora
            config.atualizado_em = agora
            print(f"  - {config.prioridade}: reset em {agora.isoformat()}")
            db.add(config)

        db.commit()

        print(f"[SLA RESET] ✅ Reset concluído com sucesso!")

        try:
            import anyio
            anyio.from_thread.run(sio.emit, "sla:reset", {
                "reset_em": agora.isoformat(),
                "configuracoes_atualizadas": len(configs),
                "timestamp": agora.isoformat(),
            })
            print(f"[SLA RESET] ✅ Evento WebSocket emitido para frontend")
        except Exception as e:
            print(f"[SLA RESET] ⚠️  Erro ao emitir evento WebSocket: {e}")

        return {
            "ok": True,
            "message": "Sistema de SLA foi completamente resetado",
            "reset_em": agora.isoformat(),
            "proximos_calculos": "Apenas chamados posteriores a este reset serão considerados",
            "configuracoes_atualizadas": len(configs),
            "cache_limpo": True,
            "memoria_limpa": True
        }
    except Exception as e:
        print(f"[SLA RESET] ❌ Erro ao resetar SLA: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao resetar SLA: {e}")


@router.post("/recalcular/p90")
def recalcular_sla_p90(db: Session = Depends(get_db)):
    """Recalcula SLA baseado em P90 (90º percentil) dos últimos 30 dias."""
    try:
        from ti.services.sla_p90_calculator import SLAP90Calculator

        resultado = SLAP90Calculator.recalcular_sla_por_prioridade(db)

        return resultado
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao recalcular SLA com P90: {e}")


@router.post("/recalcular/p90-incremental")
def recalcular_sla_p90_incremental(db: Session = Depends(get_db)):
    """Recalcula SLA baseado em P90 de forma INCREMENTAL."""
    try:
        from ti.services.sla_p90_incremental import SLAP90Incremental

        resultado = SLAP90Incremental.recalcular_incremental(db)

        return resultado
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao recalcular SLA com P90 incremental: {e}")


@router.get("/validate/config/{config_id}")
def validar_configuracao(config_id: int, db: Session = Depends(get_db)):
    """Valida uma configuração de SLA individual."""
    try:
        config = db.query(SLAConfiguration).filter(
            SLAConfiguration.id == config_id
        ).first()

        if not config:
            raise HTTPException(status_code=404, detail="Configuração de SLA não encontrada")

        validacao = SLAValidator.validar_configuracao(config)
        return validacao
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao validar configuração: {e}")


@router.get("/validate/all")
def validar_todas_configuracoes(db: Session = Depends(get_db)):
    """Valida TODAS as configurações de SLA e horários comerciais."""
    try:
        validacao = SLAValidator.validar_todas_configuracoes(db)
        return validacao
    except Exception as e:
        return {
            "sistema_valido": False,
            "erro": str(e),
            "configuracoes": [],
            "horarios_comerciais": {
                "valida": False,
                "erros": [str(e)],
                "warnings": [],
            },
            "resumo": {
                "total_configs": 0,
                "configs_validas": 0,
                "total_erros": 1,
                "total_warnings": 0,
            },
        }


@router.get("/validate/chamado/{chamado_id}")
def validar_dados_chamado(chamado_id: int, db: Session = Depends(get_db)):
    """Valida dados de um chamado específico para cálculo de SLA."""
    try:
        validacao = SLAValidator.validar_dados_chamado(db, chamado_id)
        return validacao
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feriados", response_model=list[SLAFeriadoOut])
def listar_feriados(db: Session = Depends(get_db)):
    """Lista todos os feriados cadastrados"""
    try:
        return db.query(SLAFeriado).order_by(SLAFeriado.data.asc()).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar feriados: {e}")


@router.post("/feriados", response_model=SLAFeriadoOut)
def criar_feriado(payload: SLAFeriadoCreate, db: Session = Depends(get_db)):
    """Cria um novo feriado"""
    try:
        existente = db.query(SLAFeriado).filter(
            SLAFeriado.data == payload.data
        ).first()
        if existente:
            raise HTTPException(
                status_code=400,
                detail=f"Feriado na data {payload.data} já existe"
            )

        feriado = SLAFeriado(
            data=payload.data,
            nome=payload.nome,
            descricao=payload.descricao,
            ativo=payload.ativo,
            criado_em=now_brazil_naive(),
            atualizado_em=now_brazil_naive(),
        )
        db.add(feriado)
        db.commit()
        db.refresh(feriado)
        return feriado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar feriado: {e}")


@router.patch("/feriados/{feriado_id}", response_model=SLAFeriadoOut)
def atualizar_feriado(
    feriado_id: int,
    payload: SLAFeriadoUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza um feriado existente"""
    try:
        feriado = db.query(SLAFeriado).filter(SLAFeriado.id == feriado_id).first()
        if not feriado:
            raise HTTPException(status_code=404, detail="Feriado não encontrado")

        if payload.nome is not None:
            feriado.nome = payload.nome
        if payload.descricao is not None:
            feriado.descricao = payload.descricao
        if payload.ativo is not None:
            feriado.ativo = payload.ativo

        feriado.atualizado_em = now_brazil_naive()
        db.add(feriado)
        db.commit()
        db.refresh(feriado)
        return feriado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar feriado: {e}")


@router.delete("/feriados/{feriado_id}")
def deletar_feriado(feriado_id: int, db: Session = Depends(get_db)):
    """Deleta um feriado"""
    try:
        feriado = db.query(SLAFeriado).filter(SLAFeriado.id == feriado_id).first()
        if not feriado:
            raise HTTPException(status_code=404, detail="Feriado não encontrado")

        db.delete(feriado)
        db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar feriado: {e}")


@router.get("/metrics/tempo-medio-resposta")
def obter_tempo_medio_resposta(db: Session = Depends(get_db)):
    """Retorna tempo médio de resposta (primeira resposta) para chamados fechados."""
    try:
        from ti.services.metrics import MetricsCalculator

        tempo_24h = MetricsCalculator.get_tempo_medio_resposta_24h(db)
        tempo_mes = MetricsCalculator.get_tempo_medio_resposta_mes(db)

        return {
            "tempo_medio_resposta_24h": tempo_24h,
            "tempo_medio_resposta_mes": tempo_mes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter tempo médio de resposta: {e}")


@router.get("/metrics/tempo-medio-resolucao")
def obter_tempo_medio_resolucao(db: Session = Depends(get_db)):
    """Retorna tempo médio de resolução para chamados fechados."""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import and_
        from ti.models.chamado import Chamado

        agora = now_brazil_naive()
        ontem = agora - timedelta(hours=24)
        mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        chamados_24h = db.query(Chamado).filter(
            and_(
                Chamado.data_conclusao.isnot(None),
                Chamado.data_conclusao >= ontem,
                Chamado.data_abertura.isnot(None),
            )
        ).all()

        tempos_24h = []
        for chamado in chamados_24h:
            try:
                tempo = SLACalculator.calculate_business_hours_excluding_paused(
                    chamado.id,
                    chamado.data_abertura,
                    chamado.data_conclusao,
                    db
                )
                if 0 < tempo < 168:
                    tempos_24h.append(tempo)
            except Exception:
                pass

        tempo_medio_24h = sum(tempos_24h) / len(tempos_24h) if tempos_24h else 0

        chamados_mes = db.query(Chamado).filter(
            and_(
                Chamado.data_conclusao.isnot(None),
                Chamado.data_conclusao >= mes_inicio,
                Chamado.data_abertura.isnot(None),
            )
        ).all()

        tempos_mes = []
        for chamado in chamados_mes:
            try:
                tempo = SLACalculator.calculate_business_hours_excluding_paused(
                    chamado.id,
                    chamado.data_abertura,
                    chamado.data_conclusao,
                    db
                )
                if 0 < tempo < 720:
                    tempos_mes.append(tempo)
            except Exception:
                pass

        tempo_medio_mes = sum(tempos_mes) / len(tempos_mes) if tempos_mes else 0

        return {
            "tempo_medio_resolucao_24h": round(tempo_medio_24h, 2),
            "tempo_medio_resolucao_mes": round(tempo_medio_mes, 2),
            "chamados_24h": len(tempos_24h),
            "chamados_mes": len(tempos_mes),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter tempo médio de resolução: {e}")


@router.post("/scheduler/recalcular-agora")
def recalcular_sla_agora(db: Session = Depends(get_db)):
    """Força a recalculação imediata de SLA de todos os chamados."""
    try:
        from ti.scripts.recalculate_sla_complete import SLARecalculator

        recalculator = SLARecalculator(db)
        stats = recalculator.recalculate_all(verbose=False)
        db.commit()

        return {
            "ok": True,
            "recalculados": stats["recalculados"],
            "com_erro": stats["com_erro"],
            "tempo_medio_resposta_horas": round(stats["tempo_medio_resposta_horas"], 2),
            "tempo_medio_resolucao_horas": round(stats["tempo_medio_resolucao_horas"], 2),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao recalcular SLA: {e}")


@router.get("/recommendations/p90-analysis")
def analisar_p90_recomendado(db: Session = Depends(get_db)):
    """Analisa o P90 recomendado para cada prioridade."""
    try:
        from datetime import datetime, timedelta

        agora = now_brazil_naive()
        data_inicio = agora - timedelta(days=30)

        configs = db.query(SLAConfiguration).filter(
            SLAConfiguration.ativo == True
        ).order_by(SLAConfiguration.prioridade.asc()).all()

        analise = {
            "data_analise": agora.isoformat(),
            "periodo": f"{data_inicio.isoformat()} a {agora.isoformat()}",
            "prioridades": {}
        }

        for config in configs:
            prioridade = config.prioridade

            print(f"\n[P90 ANALYSIS] Analisando prioridade: {prioridade}")
            print(f"  - SLA configurado: {config.tempo_resolucao_horas}h")

            query_filters = [
                Chamado.prioridade == prioridade,
                Chamado.data_abertura >= data_inicio,
                Chamado.data_abertura <= agora,
                Chamado.deletado_em.is_(None),
                Chamado.status.in_(["Concluído", "Cancelado"]),
                or_(Chamado.data_conclusao.isnot(None), Chamado.cancelado_em.isnot(None))
            ]

            if config.ultimo_reset_em:
                print(f"  - Filtrando apenas chamados posteriores ao reset ({config.ultimo_reset_em})")
                query_filters.append(Chamado.data_abertura >= config.ultimo_reset_em)

            chamados = db.query(Chamado).filter(and_(*query_filters)).all()

            print(f"  - Chamados encontrados: {len(chamados)}")

            if len(chamados) < 2:
                print(f"  - ⚠️ Chamados insuficientes, pulando...")
                continue

            tempos = []
            for chamado in chamados:
                try:
                    if chamado.data_abertura:
                        data_fim = chamado.data_conclusao or chamado.cancelado_em
                        if data_fim:
                            tempo = SLACalculator.calculate_business_hours_excluding_paused(
                                chamado.id,
                                chamado.data_abertura,
                                data_fim,
                                db
                            )
                            if 0 < tempo < 720:
                                tempos.append(tempo)
                except Exception as e:
                    print(f"    Erro ao processar chamado {chamado.id}: {e}")

            print(f"  - Tempos válidos: {len(tempos)}")

            if len(tempos) < 2:
                print(f"  - ⚠️ Tempos insuficientes, pulando...")
                continue

            tempos_sorted = sorted(tempos)
            p90_index = int(0.9 * (len(tempos_sorted) - 1))
            if p90_index >= len(tempos_sorted):
                p90_index = len(tempos_sorted) - 1

            p90 = tempos_sorted[p90_index]
            margem = 1.15
            p90_com_margem = p90 * margem
            media = sum(tempos) / len(tempos)
            minimo = min(tempos)
            maximo = max(tempos)

            print(f"  - Mínimo: {minimo:.1f}h")
            print(f"  - Média: {media:.1f}h")
            print(f"  - P90: {p90:.1f}h")
            print(f"  - Máximo: {maximo:.1f}h")

            dentro_atual = sum(1 for t in tempos if t <= config.tempo_resolucao_horas)
            conformidade_atual = int((dentro_atual / len(tempos)) * 100)

            dentro_p90 = sum(1 for t in tempos if t <= p90_com_margem)
            conformidade_p90 = int((dentro_p90 / len(tempos)) * 100)

            print(f"  - Conformidade SLA atual ({config.tempo_resolucao_horas}h): {conformidade_atual}%")
            print(f"  - Conformidade P90 ({int(p90_com_margem)}h): {conformidade_p90}%")
            print(f"  - Melhoria: +{conformidade_p90 - conformidade_atual}%")

            analise["prioridades"][prioridade] = {
                "sla_atual": int(config.tempo_resolucao_horas),
                "conformidade_atual": conformidade_atual,
                "chamados_analisados": len(tempos),
                "tempo_minimo": round(minimo, 2),
                "tempo_medio": round(media, 2),
                "tempo_maximo": round(maximo, 2),
                "p90": round(p90, 2),
                "p90_recomendado": int(p90_com_margem),
                "conformidade_com_p90": conformidade_p90,
                "melhoria": conformidade_p90 - conformidade_atual
            }

        return analise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao analisar P90: {e}")


@router.post("/maintenance/force-recalculate-all")
def force_recalculate_all_metrics(db: Session = Depends(get_db)):
    """
    Force completo: Limpa TODOS os caches e força recalcular TODAS as métricas.

    Use este endpoint se as métricas estiverem congeladas ou inconsistentes.
    Isso garante que os dados serão recalculados do zero na próxima requisição.
    """
    try:
        from ti.services.sla_cache import SLACacheManager
        from core.utils import now_brazil_naive

        print("\n" + "="*60)
        print("🔄 FORCE RECALCULATE: Limpando TODOS os caches...")
        print("="*60)

        # 1. Invalida TUDO do cache
        SLACacheManager.invalidate_all_sla(db)
        print("✓ Cache SLA invalidado")

        # 2. Limpa tabela de cache do banco de dados
        try:
            from ti.models.metrics_cache import MetricsCacheDB
            db.query(MetricsCacheDB).delete()
            db.commit()
            print("✓ Tabela de cache do banco de dados limpa")
        except Exception as e:
            print(f"⚠️ Erro ao limpar tabela de cache: {e}")

        # 3. Força recalculamento das métricas principais
        from ti.services.metrics import MetricsCalculator

        print("\n🔄 Recalculando métricas...")
        sla_24h = MetricsCalculator.get_sla_compliance_24h(db)
        print(f"✓ SLA Compliance 24h: {sla_24h}%")

        sla_mes = MetricsCalculator.get_sla_compliance_mes(db)
        print(f"✓ SLA Compliance Mês: {sla_mes}%")

        sla_dist = MetricsCalculator.get_sla_distribution(db)
        print(f"✓ Distribuição SLA: {sla_dist['dentro_sla']} dentro, {sla_dist['fora_sla']} fora")

        tempo_24h = MetricsCalculator.get_tempo_medio_resposta_24h(db)
        print(f"✓ Tempo Resposta 24h: {tempo_24h}")

        tempo_mes, total_mes = MetricsCalculator.get_tempo_medio_resposta_mes(db)
        print(f"✓ Tempo Resposta Mês: {tempo_mes} ({total_mes} chamados)")

        print("\n" + "="*60)
        print("✅ Recalcul completo concluído com sucesso!")
        print("="*60 + "\n")

        return {
            "ok": True,
            "message": "Todos os caches foram limpos e métricas recalculadas",
            "metrics": {
                "sla_compliance_24h": sla_24h,
                "sla_compliance_mes": sla_mes,
                "sla_distribution": sla_dist,
                "tempo_resposta_24h": tempo_24h,
                "tempo_resposta_mes": tempo_mes,
                "total_chamados_mes": total_mes,
            },
            "timestamp": now_brazil_naive().isoformat(),
            "cache_status": "cleared"
        }

    except Exception as e:
        import traceback
        print(f"\n❌ ERRO ao fazer force recalculate: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao forçar recalcul: {e}")


@router.post("/maintenance/populate-primeira-resposta")
def populate_primeira_resposta(db: Session = Depends(get_db)):
    """
    Preenche o campo data_primeira_resposta de chamados antigos usando o histórico de status.

    Este endpoint é útil para corrigir o SLA quando o campo data_primeira_resposta está vazio
    em chamados existentes. Usa o histórico de status para determinar a data da primeira resposta.

    Returns:
    - total_atualizados: Número de chamados que foram atualizados
    - total_pulados: Número de chamados sem histórico de status
    - erros: Número de erros durante o processo
    """
    try:
        from ti.models.historico_status import HistoricoStatus
        from sqlalchemy import and_

        total_atualizados = 0
        total_pulados = 0
        erros = 0

        print("\n🔄 Iniciando preenchimento de data_primeira_resposta...")

        # Busca chamados que ainda NÃO têm data_primeira_resposta
        chamados_sem_resposta = db.query(Chamado).filter(
            Chamado.data_primeira_resposta.is_(None),
            Chamado.deletado_em.is_(None)
        ).all()

        print(f"Total de chamados sem data_primeira_resposta: {len(chamados_sem_resposta)}")

        for chamado in chamados_sem_resposta:
            try:
                # Busca o primeiro histórico onde o status mudou de "Aberto"
                primeiro_historico = db.query(HistoricoStatus).filter(
                    and_(
                        HistoricoStatus.chamado_id == chamado.id,
                        HistoricoStatus.status != "Aberto"
                    )
                ).order_by(HistoricoStatus.data_inicio.asc()).first()

                if primeiro_historico and primeiro_historico.data_inicio:
                    # Atualiza o chamado com a data da primeira resposta
                    chamado.data_primeira_resposta = primeiro_historico.data_inicio
                    db.add(chamado)
                    total_atualizados += 1

                    if total_atualizados % 10 == 0:
                        db.commit()
                        print(f"✓ {total_atualizados} chamados atualizados...")
                else:
                    # Não encontrou histórico com status diferente de "Aberto"
                    total_pulados += 1

            except Exception as e:
                print(f"✗ Erro ao processar chamado {chamado.id}: {e}")
                erros += 1
                db.rollback()
                continue

        # Commit final
        db.commit()

        print(f"\n{'='*60}")
        print(f"Processo concluído!")
        print(f"✓ Chamados atualizados: {total_atualizados}")
        print(f"⊘ Chamados sem histórico: {total_pulados}")
        print(f"✗ Erros: {erros}")
        print(f"{'='*60}\n")

        # Invalida caches de SLA para forçar recálculo
        from ti.services.sla_cache import SLACacheManager
        SLACacheManager.invalidate_all_sla(db)

        return {
            "ok": True,
            "message": "Dados de primeira resposta populados com sucesso",
            "total_atualizados": total_atualizados,
            "total_pulados": total_pulados,
            "erros": erros,
            "cache_invalidado": True,
            "proxima_acao": "Os tempos de resposta serão recalculados na próxima requisição"
        }

    except Exception as e:
        print(f"Erro crítico ao popular primeira resposta: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao popular data_primeira_resposta: {e}")
