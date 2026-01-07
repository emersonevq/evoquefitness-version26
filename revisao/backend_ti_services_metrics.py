from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from ti.models.chamado import Chamado
from ti.models.historico_status import HistoricoStatus
from ti.models.sla_config import HistoricoSLA, SLAConfiguration
from ti.services.sla_cache import SLACacheManager
from core.utils import now_brazil_naive
import threading


class MetricsCalculator:
    """Calcula métricas do dashboard em tempo real"""

    @staticmethod
    def get_chamados_abertos_hoje(db: Session) -> int:
        """Retorna quantidade de chamados abertos hoje"""
        try:
            hoje = now_brazil_naive().replace(hour=0, minute=0, second=0, microsecond=0)

            count = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= hoje,
                    Chamado.status != "Cancelado"
                )
            ).count()

            return count
        except Exception as e:
            print(f"Erro ao contar chamados de hoje: {e}")
            import traceback
            traceback.print_exc()
            return 0

    @staticmethod
    def get_abertos_agora(db: Session) -> int:
        """
        Retorna quantidade de chamados ATIVOS (não concluídos nem cancelados).
        Equivalente a "todos" na página de gerenciar chamados.
        """
        try:
            count = db.query(Chamado).filter(
                and_(
                    Chamado.status != "Concluído",
                    Chamado.status != "Cancelado"
                )
            ).count()

            return count
        except Exception as e:
            print(f"Erro ao contar chamados ativos: {e}")
            import traceback
            traceback.print_exc()
            return 0

    @staticmethod
    def get_sla_compliance_24h(db: Session) -> int:
        """Calcula percentual de SLA cumprido (baseado em chamados ativos) - OTIMIZADO"""
        # Tenta cache primeiro
        cached = SLACacheManager.get(db, "sla_compliance_24h")
        if cached is not None:
            return cached

        result = MetricsCalculator._calculate_sla_compliance_24h(db)
        SLACacheManager.set(db, "sla_compliance_24h", result)
        return result

    @staticmethod
    def _calculate_sla_compliance_24h(db: Session) -> int:
        """Cálculo real de SLA 24h - otimizado sem N+1"""
        try:
            from ti.services.sla import SLACalculator
            from ti.models.historico_status import HistoricoStatus

            # 1. Carrega TODAS as configs de SLA de uma vez (não N+1)
            sla_configs = {
                config.prioridade: config
                for config in db.query(SLAConfiguration).filter(
                    SLAConfiguration.ativo == True
                ).all()
            }

            if not sla_configs:
                return 0

            # 2. Busca chamados ativos
            chamados_ativos = db.query(Chamado).filter(
                and_(
                    Chamado.status.notin_(["Concluído", "Concluido", "Cancelado"])
                )
            ).all()

            if not chamados_ativos:
                return 0

            # 3. PRÉ-CARREGA TODOS os históricos de UMA VEZ (otimização crítica)
            chamado_ids = [c.id for c in chamados_ativos]
            historicos_bulk = db.query(HistoricoStatus).filter(
                HistoricoStatus.chamado_id.in_(chamado_ids)
            ).all()

            # Cache: {chamado_id: [historicos]}
            historicos_cache = {}
            for hist in historicos_bulk:
                if hist.chamado_id not in historicos_cache:
                    historicos_cache[hist.chamado_id] = []
                historicos_cache[hist.chamado_id].append(hist)

            dentro_sla = 0
            fora_sla = 0
            agora = now_brazil_naive()

            # 4. Itera sem fazer queries adicionais (usa cache)
            for chamado in chamados_ativos:
                try:
                    sla_config = sla_configs.get(chamado.prioridade)
                    if not sla_config:
                        continue

                    # Cálculo de resolução DESCONTANDO tempo em "Em análise" (COM CACHE)
                    data_final = chamado.data_conclusao if chamado.data_conclusao else agora
                    tempo_decorrido = SLACalculator.calculate_business_hours_excluding_paused(
                        chamado.id,
                        chamado.data_abertura,
                        data_final,
                        db,
                        historicos_cache  # Passa cache para evitar queries
                    )

                    if tempo_decorrido <= sla_config.tempo_resolucao_horas:
                        dentro_sla += 1
                    else:
                        fora_sla += 1

                except Exception as e:
                    print(f"Erro ao processar chamado {chamado.id}: {e}")
                    continue

            total = dentro_sla + fora_sla
            if total == 0:
                return 0

            return int((dentro_sla / total) * 100)

        except Exception as e:
            print(f"Erro ao calcular SLA compliance 24h: {e}")
            import traceback
            traceback.print_exc()
            return 0

    @staticmethod
    def get_sla_compliance_mes(db: Session) -> int:
        """Calcula percentual de SLA cumprido para todos os chamados do mês - OTIMIZADO"""
        # Tenta cache primeiro
        cached = SLACacheManager.get(db, "sla_compliance_mes")
        if cached is not None:
            return cached

        result = MetricsCalculator._calculate_sla_compliance_mes(db)
        SLACacheManager.set(db, "sla_compliance_mes", result)
        return result

    @staticmethod
    def _calculate_sla_compliance_mes(db: Session) -> int:
        """Cálculo real de SLA mensal - otimizado sem N+1"""
        try:
            from ti.services.sla import SLACalculator
            from ti.models.historico_status import HistoricoStatus

            agora = now_brazil_naive()
            mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # 1. Carrega TODAS as configs de SLA de uma vez
            sla_configs = {
                config.prioridade: config
                for config in db.query(SLAConfiguration).filter(
                    SLAConfiguration.ativo == True
                ).all()
            }

            if not sla_configs:
                return 0

            # 2. Busca chamados do mês que tiveram resposta
            chamados_mes = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= mes_inicio,
                    Chamado.data_abertura <= agora,
                    Chamado.status != "Cancelado",
                    Chamado.data_primeira_resposta.isnot(None)
                )
            ).all()

            if not chamados_mes:
                return 0

            # 3. PRÉ-CARREGA TODOS os históricos de UMA VEZ (otimização crítica)
            chamado_ids = [c.id for c in chamados_mes]
            historicos_bulk = db.query(HistoricoStatus).filter(
                HistoricoStatus.chamado_id.in_(chamado_ids)
            ).all()

            # Cache: {chamado_id: [historicos]}
            historicos_cache = {}
            for hist in historicos_bulk:
                if hist.chamado_id not in historicos_cache:
                    historicos_cache[hist.chamado_id] = []
                historicos_cache[hist.chamado_id].append(hist)

            dentro_sla = 0
            fora_sla = 0

            # 4. Itera sem fazer queries adicionais (usa cache)
            for chamado in chamados_mes:
                try:
                    sla_config = sla_configs.get(chamado.prioridade)
                    if not sla_config:
                        continue

                    # Define data final para cálculo
                    data_final = chamado.data_conclusao if chamado.data_conclusao else agora

                    # Calcula tempo de resolução em horas de negócio DESCONTANDO "Em análise" (COM CACHE)
                    tempo_resolucao_horas = SLACalculator.calculate_business_hours_excluding_paused(
                        chamado.id,
                        chamado.data_abertura,
                        data_final,
                        db,
                        historicos_cache  # Passa cache para evitar queries
                    )

                    # Verifica se atendeu o SLA de resolução
                    if tempo_resolucao_horas <= sla_config.tempo_resolucao_horas:
                        dentro_sla += 1
                    else:
                        fora_sla += 1

                except Exception as e:
                    print(f"Erro ao processar chamado {chamado.id}: {e}")
                    continue

            total = dentro_sla + fora_sla
            if total == 0:
                return 0

            return int((dentro_sla / total) * 100)

        except Exception as e:
            print(f"Erro ao calcular SLA compliance mês: {e}")
            import traceback
            traceback.print_exc()
            return 0

    @staticmethod
    def get_sla_distribution(db: Session) -> dict:
        """Retorna distribuição de SLA (dentro/fora) - SINCRONIZADO COM CARD SLA"""
        # Tenta cache primeiro
        cached = SLACacheManager.get(db, "sla_distribution")
        if cached is not None:
            return cached

        result = MetricsCalculator._calculate_sla_distribution(db)
        SLACacheManager.set(db, "sla_distribution", result)
        return result

    @staticmethod
    def _calculate_sla_distribution(db: Session) -> dict:
        """Cálculo real - usa MESMOS critérios que get_sla_compliance_mes"""
        try:
            from ti.services.sla import SLACalculator

            agora = now_brazil_naive()
            mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # IMPORTANTE: Usa MESMOS chamados que o card SLA (todos do mês)
            chamados_mes = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= mes_inicio,
                    Chamado.data_abertura <= agora,
                    Chamado.status != "Cancelado",
                    Chamado.data_primeira_resposta.isnot(None)
                )
            ).all()

            # Carrega configs de SLA de uma vez (sem N+1)
            sla_configs = {
                config.prioridade: config
                for config in db.query(SLAConfiguration).filter(
                    SLAConfiguration.ativo == True
                ).all()
            }

            dentro_sla = 0
            fora_sla = 0

            for chamado in chamados_mes:
                try:
                    sla_config = sla_configs.get(chamado.prioridade)
                    if not sla_config:
                        continue

                    data_final = chamado.data_conclusao if chamado.data_conclusao else agora
                    tempo_resolucao_horas = SLACalculator.calculate_business_hours_excluding_paused(
                        chamado.id,
                        chamado.data_abertura,
                        data_final,
                        db
                    )

                    if tempo_resolucao_horas <= sla_config.tempo_resolucao_horas:
                        dentro_sla += 1
                    else:
                        fora_sla += 1

                except Exception as e:
                    print(f"Erro ao processar chamado {chamado.id}: {e}")
                    continue

            total = dentro_sla + fora_sla
            if total == 0:
                return {
                    "dentro_sla": 0,
                    "fora_sla": 0,
                    "percentual_dentro": 0,
                    "percentual_fora": 0,
                    "total": 0
                }

            percentual_dentro = int((dentro_sla / total) * 100)
            percentual_fora = int((fora_sla / total) * 100)

            return {
                "dentro_sla": dentro_sla,
                "fora_sla": fora_sla,
                "percentual_dentro": percentual_dentro,
                "percentual_fora": percentual_fora,
                "total": total
            }

        except Exception as e:
            print(f"Erro ao calcular distribuição SLA: {e}")
            import traceback
            traceback.print_exc()
            return {
                "dentro_sla": 0,
                "fora_sla": 0,
                "percentual_dentro": 0,
                "percentual_fora": 0,
                "total": 0
            }

    @staticmethod
    def get_dashboard_metrics(db: Session) -> dict:
        """Retorna todos os métricas do dashboard"""
        try:
            sla_compliance = MetricsCalculator.get_sla_compliance_mes(db)
            abertos_agora = MetricsCalculator.get_abertos_agora(db)

            return {
                "sla_compliance_mes": sla_compliance,
                "abertos_agora": abertos_agora,
            }
        except Exception as e:
            print(f"Erro crítico ao calcular métricas do dashboard: {e}")
            import traceback
            traceback.print_exc()
            return {
                "sla_compliance_mes": 0,
                "abertos_agora": 0,
            }
