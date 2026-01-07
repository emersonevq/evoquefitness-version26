"""
Unified SLA Metrics Calculator

Single source of truth for all SLA metrics. All metrics derive from:
1. Calculate SLA distribution (contar chamados dentro/fora SLA)
2. Derive percentages from distribuição
3. Cache calculated results

This ensures consistency across all endpoints.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ti.models.chamado import Chamado
from ti.models.sla_config import SLAConfiguration
from ti.models.historico_status import HistoricoStatus
from ti.services.sla import SLACalculator
from ti.services.sla_status import SLAStatus
from core.utils import now_brazil_naive


class UnifiedSLAMetricsCalculator:
    """
    Calcula todas as métricas de SLA a partir de uma única distribuição.
    
    Estratégia:
    1. Carregar TODOS os chamados do período
    2. Classificar cada um como dentro/fora SLA
    3. Derivar percentuais dessa classificação
    4. Cache dos resultados
    """
    
    @staticmethod
    def calculate_sla_distribution_period(
        db: Session,
        start_date: datetime,
        end_date: datetime
    ) -> dict:
        """
        Calcula distribuição de SLA para um período específico.
        
        FONTE ÚNICA DE VERDADE para todas as métricas.
        
        Args:
            db: Sessão do banco de dados
            start_date: Data inicial do período
            end_date: Data final do período
            
        Returns:
            {
                "total": int,
                "dentro_sla": int,
                "fora_sla": int,
                "percentual_dentro": int,
                "percentual_fora": int,
                "data_inicio": datetime,
                "data_fim": datetime,
                "timestamp_calculo": datetime
            }
        """
        try:
            # Carrega todas as configs de SLA
            sla_configs = {
                config.prioridade: config
                for config in db.query(SLAConfiguration).filter(
                    SLAConfiguration.ativo == True
                ).all()
            }
            
            if not sla_configs:
                return {
                    "total": 0,
                    "dentro_sla": 0,
                    "fora_sla": 0,
                    "percentual_dentro": 0,
                    "percentual_fora": 0,
                    "data_inicio": start_date,
                    "data_fim": end_date,
                    "timestamp_calculo": now_brazil_naive()
                }
            
            # Busca chamados do período com LIMIT para evitar carregar tudo na memória
            # Processa em chunks de 1000 chamados por vez
            query = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= start_date,
                    Chamado.data_abertura <= end_date,
                    Chamado.status != "Cancelado",
                    Chamado.data_primeira_resposta.isnot(None)
                )
            ).order_by(Chamado.id)

            total_count = query.count()

            if total_count == 0:
                return {
                    "total": 0,
                    "dentro_sla": 0,
                    "fora_sla": 0,
                    "percentual_dentro": 0,
                    "percentual_fora": 0,
                    "data_inicio": start_date,
                    "data_fim": end_date,
                    "timestamp_calculo": now_brazil_naive()
                }

            # Classifica em chunks para otimizar memória e conexão
            dentro_sla = 0
            fora_sla = 0
            chunk_size = 500

            for offset in range(0, total_count, chunk_size):
                # Carrega chunk de chamados
                chamados_chunk = query.offset(offset).limit(chunk_size).all()

                # PRÉ-CARREGA históricos APENAS para este chunk
                chamado_ids = [c.id for c in chamados_chunk]
                historicos_bulk = db.query(HistoricoStatus).filter(
                    HistoricoStatus.chamado_id.in_(chamado_ids)
                ).all()

                historicos_cache = {}
                for hist in historicos_bulk:
                    if hist.chamado_id not in historicos_cache:
                        historicos_cache[hist.chamado_id] = []
                    historicos_cache[hist.chamado_id].append(hist)

                # Processa chamados deste chunk
                for chamado in chamados_chunk:
                    try:
                        sla_config = sla_configs.get(chamado.prioridade)
                        if not sla_config:
                            continue

                        # Determina data final para cálculo
                        data_abertura = chamado.data_abertura or end_date
                        data_final = chamado.data_conclusao if chamado.data_conclusao else end_date

                        # Calcula tempo de resolução excluindo pausas
                        tempo_resolucao = SLACalculator.calculate_business_hours_excluding_paused(
                            chamado.id,
                            data_abertura,
                            data_final,
                            db,
                            historicos_cache
                        )

                        # Classifica
                        if tempo_resolucao <= sla_config.tempo_resolucao_horas:
                            dentro_sla += 1
                        else:
                            fora_sla += 1

                    except Exception as e:
                        print(f"Erro ao processar chamado {chamado.id}: {e}")
                        continue

                # Limpa sessão entre chunks para liberar memória
                db.expunge_all()
            
            total = dentro_sla + fora_sla
            
            if total == 0:
                return {
                    "total": 0,
                    "dentro_sla": 0,
                    "fora_sla": 0,
                    "percentual_dentro": 0,
                    "percentual_fora": 0,
                    "data_inicio": start_date,
                    "data_fim": end_date,
                    "timestamp_calculo": now_brazil_naive()
                }
            
            percentual_dentro = int((dentro_sla / total) * 100)
            percentual_fora = int((fora_sla / total) * 100)
            
            return {
                "total": total,
                "dentro_sla": dentro_sla,
                "fora_sla": fora_sla,
                "percentual_dentro": percentual_dentro,
                "percentual_fora": percentual_fora,
                "data_inicio": start_date,
                "data_fim": end_date,
                "timestamp_calculo": now_brazil_naive()
            }
        
        except Exception as e:
            print(f"Erro ao calcular distribuição SLA: {e}")
            import traceback
            traceback.print_exc()
            return {
                "total": 0,
                "dentro_sla": 0,
                "fora_sla": 0,
                "percentual_dentro": 0,
                "percentual_fora": 0,
                "data_inicio": start_date,
                "data_fim": end_date,
                "timestamp_calculo": now_brazil_naive()
            }
    
    @staticmethod
    def get_sla_compliance_month(db: Session) -> dict:
        """
        Retorna compliance de SLA para o mês atual.
        
        Derivado da distribuição, não é cálculo independente.
        """
        agora = now_brazil_naive()
        mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        dist = UnifiedSLAMetricsCalculator.calculate_sla_distribution_period(
            db, mes_inicio, agora
        )
        
        return {
            "percentual": dist["percentual_dentro"],
            "total": dist["total"],
            "dentro_sla": dist["dentro_sla"],
            "fora_sla": dist["fora_sla"],
            "periodo": "mes",
            "timestamp": now_brazil_naive().isoformat()
        }
    
    @staticmethod
    def get_sla_compliance_24h(db: Session) -> dict:
        """
        Retorna compliance de SLA para as últimas 24 horas.
        
        Nota: 24h usa critério diferente - apenas chamados ATIVOS (não concluídos)
        Portanto, tem seu próprio cálculo, mas mesmo princípio.
        """
        try:
            agora = now_brazil_naive()
            ontem = agora - timedelta(hours=24)
            
            # Carrega configs
            sla_configs = {
                config.prioridade: config
                for config in db.query(SLAConfiguration).filter(
                    SLAConfiguration.ativo == True
                ).all()
            }
            
            if not sla_configs:
                return {
                    "percentual": 0,
                    "total": 0,
                    "dentro_sla": 0,
                    "fora_sla": 0,
                    "periodo": "24h",
                    "timestamp": now_brazil_naive().isoformat()
                }
            
            # Busca chamados ATIVOS (apenas que foram abertos nos últimos 30 dias para limite razoável)
            data_limite_30d = agora - timedelta(days=30)
            query_ativos = db.query(Chamado).filter(
                and_(
                    Chamado.status.notin_(["Concluido", "Cancelado"]),
                    Chamado.data_abertura >= data_limite_30d
                )
            ).order_by(Chamado.id)

            total_ativos = query_ativos.count()

            if total_ativos == 0:
                return {
                    "percentual": 0,
                    "total": 0,
                    "dentro_sla": 0,
                    "fora_sla": 0,
                    "periodo": "24h",
                    "timestamp": now_brazil_naive().isoformat()
                }

            dentro_sla = 0
            fora_sla = 0
            chunk_size = 500

            # Processa em chunks
            for offset in range(0, total_ativos, chunk_size):
                chamados_chunk = query_ativos.offset(offset).limit(chunk_size).all()

                # PRÉ-CARREGA históricos para este chunk
                chamado_ids = [c.id for c in chamados_chunk]
                historicos_bulk = db.query(HistoricoStatus).filter(
                    HistoricoStatus.chamado_id.in_(chamado_ids)
                ).all()

                historicos_cache = {}
                for hist in historicos_bulk:
                    if hist.chamado_id not in historicos_cache:
                        historicos_cache[hist.chamado_id] = []
                    historicos_cache[hist.chamado_id].append(hist)

                for chamado in chamados_chunk:
                    try:
                        sla_config = sla_configs.get(chamado.prioridade)
                        if not sla_config:
                            continue

                        # Usa data atual como final (chamados ainda abertos)
                        data_abertura = chamado.data_abertura or agora
                        tempo_resolucao = SLACalculator.calculate_business_hours_excluding_paused(
                            chamado.id,
                            data_abertura,
                            agora,
                            db,
                            historicos_cache
                        )

                        if tempo_resolucao <= sla_config.tempo_resolucao_horas:
                            dentro_sla += 1
                        else:
                            fora_sla += 1

                    except Exception as e:
                        print(f"Erro ao processar chamado {chamado.id}: {e}")
                        continue

                # Limpa sessão entre chunks
                db.expunge_all()

            total = dentro_sla + fora_sla
            percentual = int((dentro_sla / total) * 100) if total > 0 else 0
            
            return {
                "percentual": percentual,
                "total": total,
                "dentro_sla": dentro_sla,
                "fora_sla": fora_sla,
                "periodo": "24h",
                "timestamp": now_brazil_naive().isoformat()
            }
        
        except Exception as e:
            print(f"Erro ao calcular SLA 24h: {e}")
            import traceback
            traceback.print_exc()
            return {
                "percentual": 0,
                "total": 0,
                "dentro_sla": 0,
                "fora_sla": 0,
                "periodo": "24h",
                "timestamp": now_brazil_naive().isoformat()
            }
