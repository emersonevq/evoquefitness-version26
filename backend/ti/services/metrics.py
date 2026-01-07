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
        """Retorna quantidade de chamados abertos hoje (do cache incremental)"""
        try:
            from ti.services.cache_manager_incremental import ChamadosTodayCounter
            return ChamadosTodayCounter.get_count(db)
        except Exception as e:
            print(f"Erro ao obter contador de hoje: {e}")
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
                    Chamado.status != "Concluido",
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
    def get_tempo_medio_resposta_24h(db: Session) -> str:
        """Calcula tempo médio de PRIMEIRA resposta das últimas 24h em horas de negócio"""
        from ti.services.sla import SLACalculator

        agora = now_brazil_naive()
        ontem = agora - timedelta(hours=24)

        try:
            # Busca chamados das últimas 24h que tiveram primeira resposta
            chamados = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= ontem,
                    Chamado.status != "Cancelado",
                    Chamado.data_primeira_resposta.isnot(None),
                    Chamado.data_primeira_resposta >= ontem
                )
            ).all()

            if not chamados:
                return "—"

            # Calcula os tempos em horas de NEGÓCIO
            tempos = []
            for chamado in chamados:
                if chamado.data_primeira_resposta and chamado.data_abertura:
                    # Usa horas de NEGÓCIO
                    horas = SLACalculator.calculate_business_hours(
                        chamado.data_abertura,
                        chamado.data_primeira_resposta,
                        db
                    )
                    # Filtro de sanidade: apenas valores entre 0 e 72h
                    if 0 <= horas <= 72:
                        tempos.append(horas)

            if not tempos:
                return "—"

            media_horas = sum(tempos) / len(tempos)

            if media_horas < 1:
                minutos = int(media_horas * 60)
                return f"{minutos}m"
            else:
                horas = int(media_horas)
                minutos = int((media_horas - horas) * 60)
                return f"{horas}h {minutos}m" if minutos > 0 else f"{horas}h"
        except Exception as e:
            print(f"Erro ao calcular tempo de resposta 24h: {e}")
            import traceback
            traceback.print_exc()
            return "—"

    @staticmethod
    def get_tempo_medio_resposta_mes(db: Session) -> tuple[str, int]:
        """Calcula tempo médio de PRIMEIRA resposta deste mês usando Chamado.data_primeira_resposta"""
        from ti.services.sla import SLACalculator

        agora = now_brazil_naive()
        mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        try:
            # Busca chamados do mês que já tiveram primeira resposta
            chamados = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= mes_inicio,
                    Chamado.data_abertura <= agora,
                    Chamado.status != "Cancelado",
                    Chamado.data_primeira_resposta.isnot(None)
                )
            ).all()

            # Conta total de chamados do mês (mesmo sem resposta)
            total_chamados_mes = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= mes_inicio,
                    Chamado.data_abertura <= agora,
                    Chamado.status != "Cancelado"
                )
            ).count()

            if not chamados:
                return "—", total_chamados_mes

            # Calcula os tempos em horas de NEGÓCIO
            tempos = []
            for chamado in chamados:
                if chamado.data_primeira_resposta and chamado.data_abertura:
                    # Usa horas de NEGÓCIO (não clock time)
                    horas = SLACalculator.calculate_business_hours(
                        chamado.data_abertura,
                        chamado.data_primeira_resposta,
                        db
                    )

                    # Filtro de sanidade: apenas valores entre 0 e 72h
                    if 0 <= horas <= 72:
                        tempos.append(horas)

            if not tempos:
                return "—", total_chamados_mes

            media_horas = sum(tempos) / len(tempos)

            # Formata o resultado
            if media_horas < 1:
                return f"{int(media_horas * 60)}m", total_chamados_mes
            else:
                horas = int(media_horas)
                minutos = int((media_horas - horas) * 60)
                return (f"{horas}h {minutos}m" if minutos > 0 else f"{horas}h"), total_chamados_mes

        except Exception as e:
            print(f"Erro ao calcular tempo de resposta do mês: {e}")
            import traceback
            traceback.print_exc()
            return "—", 0

    @staticmethod
    def get_sla_compliance_24h(db: Session) -> int:
        """Calcula percentual de SLA cumprido (baseado em chamados ativos) - usa fonte unificada"""
        from ti.services.sla_metrics_unified import UnifiedSLAMetricsCalculator

        # Tenta cache primeiro
        cached = SLACacheManager.get(db, "sla_compliance_24h")
        if cached is not None:
            print(f"[CACHE HIT] SLA Compliance 24h: {cached}%")
            return cached

        print("[CACHE MISS] SLA Compliance 24h calculando...")
        result_dict = UnifiedSLAMetricsCalculator.get_sla_compliance_24h(db)
        result = result_dict["percentual"]
        print(f"[CACHE SET] SLA Compliance 24h: {result}%")
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
                    Chamado.status.notin_(["Concluido", "Cancelado"])
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
                    data_abertura = chamado.data_abertura or agora
                    data_final = chamado.data_conclusao if chamado.data_conclusao else agora
                    tempo_decorrido = SLACalculator.calculate_business_hours_excluding_paused(
                        chamado.id,
                        data_abertura,
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
        """Calcula percentual de SLA cumprido para todos os chamados do mês - usa fonte unificada"""
        from ti.services.sla_metrics_unified import UnifiedSLAMetricsCalculator

        # Tenta cache primeiro
        cached = SLACacheManager.get(db, "sla_compliance_mes")
        if cached is not None:
            print(f"[CACHE HIT] SLA Compliance Mês: {cached}%")
            return cached

        print("[CACHE MISS] SLA Compliance Mês calculando...")
        result_dict = UnifiedSLAMetricsCalculator.get_sla_compliance_month(db)
        result = result_dict["percentual"]
        print(f"[CACHE SET] SLA Compliance Mês: {result}%")
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
                    data_abertura = chamado.data_abertura or agora
                    data_final = chamado.data_conclusao if chamado.data_conclusao else agora

                    # Calcula tempo de resolução em horas de negócio DESCONTANDO "Em análise" (COM CACHE)
                    tempo_resolucao_horas = SLACalculator.calculate_business_hours_excluding_paused(
                        chamado.id,
                        data_abertura,
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
    def get_chamados_hoje_count(db: Session) -> int:
        """Retorna quantidade de chamados de hoje"""
        return MetricsCalculator.get_chamados_abertos_hoje(db)

    @staticmethod
    def get_comparacao_ontem(db: Session) -> dict:
        """Compara chamados de hoje vs ontem"""
        try:
            agora = now_brazil_naive()
            hoje_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            ontem_inicio = (agora - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            ontem_fim = hoje_inicio

            chamados_hoje = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= hoje_inicio,
                    Chamado.status != "Cancelado"
                )
            ).count()

            chamados_ontem = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= ontem_inicio,
                    Chamado.data_abertura < ontem_fim,
                    Chamado.status != "Cancelado"
                )
            ).count()

            if chamados_ontem == 0:
                percentual = 0
            else:
                percentual = int(((chamados_hoje - chamados_ontem) / chamados_ontem) * 100)

            return {
                "hoje": chamados_hoje,
                "ontem": chamados_ontem,
                "percentual": percentual,
                "direcao": "up" if percentual >= 0 else "down"
            }
        except Exception as e:
            print(f"Erro ao calcular comparação com ontem: {e}")
            import traceback
            traceback.print_exc()
            return {"hoje": 0, "ontem": 0, "percentual": 0, "direcao": "up"}

    @staticmethod
    def get_tempo_resolucao_media_30dias(db: Session) -> str:
        """Calcula tempo médio de resolução dos últimos 30 dias"""
        agora = now_brazil_naive()
        trinta_dias_atras = agora - timedelta(days=30)
        
        chamados = db.query(Chamado).filter(
            and_(
                Chamado.data_abertura >= trinta_dias_atras,
                Chamado.data_conclusao.isnot(None),
            )
        ).all()
        
        if not chamados:
            return "—"
        
        tempos = []
        for chamado in chamados:
            if chamado.data_conclusao and chamado.data_abertura:
                delta = chamado.data_conclusao - chamado.data_abertura
                horas = delta.total_seconds() / 3600
                tempos.append(horas)
        
        if not tempos:
            return "—"
        
        media_horas = sum(tempos) / len(tempos)
        
        horas = int(media_horas)
        minutos = int((media_horas - horas) * 60)
        return f"{horas}h {minutos}m" if minutos > 0 else f"{horas}h"

    @staticmethod
    def get_chamados_por_dia(db: Session, dias: int = 7, statuses: list[str] | None = None) -> list[dict]:
        """Retorna quantidade de chamados por dia dos últimos N dias, separado por status

        Args:
            db: Session do banco de dados
            dias: Número de dias a retornar
            statuses: Lista de status para filtrar (ex: ["Aberto", "Em andamento"])
                     Se None ou vazio, mostra todos os status
        """
        agora = now_brazil_naive()
        dias_atras = agora - timedelta(days=dias)

        dias_data = []
        for i in range(dias):
            dia = agora - timedelta(days=dias - 1 - i)
            dias_data.append(dia.replace(hour=0, minute=0, second=0, microsecond=0))

        # Status disponíveis
        status_disponiveis = ["Aberto", "Em andamento", "Em análise", "Concluído", "Cancelado"]
        statuses_para_usar = statuses if statuses and len(statuses) > 0 else status_disponiveis

        resultado = []
        for i, dia_inicio in enumerate(dias_data):
            dia_fim = dia_inicio + timedelta(days=1)

            dados_dia = {
                "dia": ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"][dia_inicio.weekday()],
                "data": dia_inicio.strftime("%Y-%m-%d"),
            }

            # Contar por status
            for status in statuses_para_usar:
                count = db.query(Chamado).filter(
                    and_(
                        Chamado.data_abertura >= dia_inicio,
                        Chamado.data_abertura < dia_fim,
                        Chamado.status == status
                    )
                ).count()

                status_key = status.lower().replace(" ", "_").replace("á", "a")
                dados_dia[status_key] = count

            resultado.append(dados_dia)

        return resultado

    @staticmethod
    def get_chamados_por_semana(db: Session, semanas: int = 4, statuses: list[str] | None = None) -> list[dict]:
        """Retorna quantidade de chamados por semana dos últimos N semanas, separado por status

        Args:
            db: Session do banco de dados
            semanas: Número de semanas a retornar
            statuses: Lista de status para filtrar (ex: ["Aberto", "Em andamento"])
                     Se None ou vazio, mostra todos os status
        """
        agora = now_brazil_naive()
        resultado = []

        # Status disponíveis
        status_disponiveis = ["Aberto", "Em andamento", "Em análise", "Concluído", "Cancelado"]
        statuses_para_usar = statuses if statuses and len(statuses) > 0 else status_disponiveis

        for i in range(semanas):
            semana_num = semanas - i
            semana_inicio = agora - timedelta(weeks=i)
            semana_inicio = semana_inicio - timedelta(days=semana_inicio.weekday())
            semana_inicio = semana_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
            semana_fim = semana_inicio + timedelta(days=7)

            dados_semana = {
                "semana": f"S{semana_num}",
            }

            # Contar por status
            for status in statuses_para_usar:
                count = db.query(Chamado).filter(
                    and_(
                        Chamado.data_abertura >= semana_inicio,
                        Chamado.data_abertura < semana_fim,
                        Chamado.status == status
                    )
                ).count()

                status_key = status.lower().replace(" ", "_").replace("á", "a")
                dados_semana[status_key] = count

            resultado.insert(0, dados_semana)

        return resultado

    @staticmethod
    def get_chamados_por_mes(db: Session, meses: int = 3, statuses: list[str] | None = None) -> list[dict]:
        """Retorna quantidade de chamados por mês dos últimos N meses, separado por status

        Args:
            db: Session do banco de dados
            meses: Número de meses a retornar
            statuses: Lista de status para filtrar (ex: ["Aberto", "Em andamento"])
                     Se None ou vazio, mostra todos os status
        """
        agora = now_brazil_naive()
        resultado = []

        # Status disponíveis no sistema
        status_disponiveis = ["Aberto", "Em andamento", "Em análise", "Concluído", "Cancelado"]

        # Se statuses foi especificado, filtra apenas os selecionados
        statuses_para_usar = statuses if statuses and len(statuses) > 0 else status_disponiveis

        for i in range(meses):
            mes_num = meses - i
            # Calcular o primeiro dia do mês i meses atrás
            data_temp = agora - timedelta(days=30 * i)
            mes_inicio = data_temp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Calcular o primeiro dia do próximo mês
            if mes_inicio.month == 12:
                mes_fim = mes_inicio.replace(year=mes_inicio.year + 1, month=1)
            else:
                mes_fim = mes_inicio.replace(month=mes_inicio.month + 1)

            # Contar por status
            dados_mes = {
                "mes": mes_inicio.strftime("%b %Y"),
                "data_iso": mes_inicio.strftime("%Y-%m"),
            }

            for status in statuses_para_usar:
                count = db.query(Chamado).filter(
                    and_(
                        Chamado.data_abertura >= mes_inicio,
                        Chamado.data_abertura < mes_fim,
                        Chamado.status == status
                    )
                ).count()

                # Normaliza nome do status para key segura (remova espaços e caracteres especiais)
                status_key = status.lower().replace(" ", "_").replace("á", "a")
                dados_mes[status_key] = count

            resultado.insert(0, dados_mes)

        return resultado

    @staticmethod
    def get_sla_distribution(db: Session) -> dict:
        """Retorna distribuição de SLA (dentro/fora) - usa fonte unificada"""
        from ti.services.sla_metrics_unified import UnifiedSLAMetricsCalculator

        # Tenta cache primeiro
        cached = SLACacheManager.get(db, "sla_distribution")
        if cached is not None:
            print(f"[CACHE HIT] SLA Distribution: {cached}")
            # Valida e extrai se estiver wrapped em {'value': ...}
            if isinstance(cached, dict) and 'value' in cached and len(cached) == 1:
                cached = cached['value']
            return cached

        print("[CACHE MISS] SLA Distribution calculando...")

        agora = now_brazil_naive()
        mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = UnifiedSLAMetricsCalculator.calculate_sla_distribution_period(
            db, mes_inicio, agora
        )

        # Formata resultado para compatibilidade
        formatted_result = {
            "dentro_sla": result["dentro_sla"],
            "fora_sla": result["fora_sla"],
            "percentual_dentro": result["percentual_dentro"],
            "percentual_fora": result["percentual_fora"],
            "total": result["total"]
        }

        print(f"[CACHE SET] SLA Distribution: {formatted_result}")
        SLACacheManager.set(db, "sla_distribution", formatted_result)
        return formatted_result

    @staticmethod
    def _calculate_sla_distribution(db: Session) -> dict:
        """Cálculo real - usa MESMOS critérios que get_sla_compliance_mes - OTIMIZADO"""
        try:
            from ti.services.sla import SLACalculator
            from ti.models.historico_status import HistoricoStatus

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

            # PRÉ-CARREGA TODOS os históricos de UMA VEZ (otimização crítica)
            chamado_ids = [c.id for c in chamados_mes]
            historicos_bulk = db.query(HistoricoStatus).filter(
                HistoricoStatus.chamado_id.in_(chamado_ids)
            ).all() if chamado_ids else []

            # Cache: {chamado_id: [historicos]}
            historicos_cache = {}
            for hist in historicos_bulk:
                if hist.chamado_id not in historicos_cache:
                    historicos_cache[hist.chamado_id] = []
                historicos_cache[hist.chamado_id].append(hist)

            dentro_sla = 0
            fora_sla = 0

            for chamado in chamados_mes:
                try:
                    sla_config = sla_configs.get(chamado.prioridade)
                    if not sla_config:
                        continue

                    data_abertura = chamado.data_abertura or agora
                    data_final = chamado.data_conclusao if chamado.data_conclusao else agora
                    tempo_resolucao_horas = SLACalculator.calculate_business_hours_excluding_paused(
                        chamado.id,
                        data_abertura,
                        data_final,
                        db,
                        historicos_cache
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
    def get_performance_metrics(db: Session) -> dict:
        """Retorna métricas de performance (últimos 30 dias) - CORRIGIDO"""
        try:
            from ti.services.sla import SLACalculator

            agora = now_brazil_naive()
            trinta_dias_atras = agora - timedelta(days=30)

            # Busca chamados dos últimos 30 dias
            chamados_30dias = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= trinta_dias_atras,
                    Chamado.status != "Cancelado"
                )
            ).all()

            # ===== TEMPO MÉDIO DE RESOLUÇÃO (horas de negócio SEM "Em análise") =====
            tempos_resolucao = []
            for chamado in chamados_30dias:
                if chamado.data_conclusao and chamado.data_abertura:
                    # Usa horas de NEGÓCIO DESCONTANDO "Em análise"
                    horas = SLACalculator.calculate_business_hours_excluding_paused(
                        chamado.id,
                        chamado.data_abertura,
                        chamado.data_conclusao,
                        db
                    )
                    tempos_resolucao.append(horas)

            tempo_resolucao_medio = sum(tempos_resolucao) / len(tempos_resolucao) if tempos_resolucao else 0
            horas = int(tempo_resolucao_medio)
            minutos = int((tempo_resolucao_medio - horas) * 60)
            tempo_resolucao_str = f"{horas}h {minutos}m" if minutos > 0 else f"{horas}h" if horas > 0 else "—"

            # ===== TEMPO MÉDIO DE PRIMEIRA RESPOSTA =====
            # Usa Chamado.data_primeira_resposta (fonte confiável)
            tempos_primeira_resposta = []
            for chamado in chamados_30dias:
                if chamado.data_primeira_resposta and chamado.data_abertura:
                    # Usa horas de NEGÓCIO (não desconta nada para primeira resposta)
                    horas = SLACalculator.calculate_business_hours(
                        chamado.data_abertura,
                        chamado.data_primeira_resposta,
                        db
                    )
                    # Filtro de sanidade: máximo 72h
                    if 0 <= horas <= 72:
                        tempos_primeira_resposta.append(horas)

            tempo_primeira_resposta_medio = sum(tempos_primeira_resposta) / len(tempos_primeira_resposta) if tempos_primeira_resposta else 0

            # Formata corretamente: horas e minutos
            if tempo_primeira_resposta_medio > 0:
                hrs = int(tempo_primeira_resposta_medio)
                mins = int((tempo_primeira_resposta_medio - hrs) * 60)
                tempo_primeira_resposta_str = f"{hrs}h {mins}m" if mins > 0 else f"{hrs}h"
            else:
                tempo_primeira_resposta_str = "—"

            # ===== TAXA DE REABERTURAS =====
            # Calcula % de chamados que foram reaberlos (status != Concluído em algum momento)
            # Para simplificar: verifica chamados com múltiplas transições
            chamados_reaberlos = 0
            for chamado in chamados_30dias:
                historicos = db.query(HistoricoStatus).filter(
                    HistoricoStatus.chamado_id == chamado.id
                ).count()
                # Se tem mais de 5 históricos, provavelmente foi reaberto
                if historicos > 5:
                    chamados_reaberlos += 1

            total_com_historico = sum(
                1 for c in chamados_30dias
                if db.query(HistoricoStatus).filter(
                    HistoricoStatus.chamado_id == c.id
                ).count() > 0
            )
            taxa_reaberturas = int((chamados_reaberlos / total_com_historico * 100)) if total_com_historico > 0 else 0

            # ===== CHAMADOS EM BACKLOG =====
            # Chamados que estão aguardando (congelados)
            chamados_backlog = db.query(Chamado).filter(
                and_(
                    Chamado.status.in_(["Aguardando", "Em análise"]),
                    Chamado.status != "Cancelado"
                )
            ).count()

            return {
                "tempo_resolucao_medio": tempo_resolucao_str,
                "primeira_resposta_media": tempo_primeira_resposta_str,
                "taxa_reaberturas": f"{taxa_reaberturas}%",
                "chamados_backlog": chamados_backlog
            }

        except Exception as e:
            print(f"Erro ao calcular métricas de performance: {e}")
            import traceback
            traceback.print_exc()
            return {
                "tempo_resolucao_medio": "—",
                "primeira_resposta_media": "—",
                "taxa_reaberturas": "0%",
                "chamados_backlog": 0
            }

    @staticmethod
    def debug_tempo_resposta(db: Session, periodo: str = "mes"):
        """
        Debug: mostra os dados brutos de tempo de resposta
        periodo: "mes", "24h" ou "30dias"
        """
        agora = now_brazil_naive()

        if periodo == "mes":
            inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif periodo == "24h":
            inicio = agora - timedelta(hours=24)
        else:  # 30dias
            inicio = agora - timedelta(days=30)

        historicos = db.query(HistoricoStatus).filter(
            and_(
                HistoricoStatus.created_at >= inicio,
                HistoricoStatus.status.in_(["Em Atendimento", "Em análise", "Em andamento"])
            )
        ).all()

        print(f"\n{'='*100}")
        print(f"DEBUG: Tempo de Resposta ({periodo})")
        print(f"Período: {inicio.strftime('%Y-%m-%d %H:%M:%S')} a {agora.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total de registros encontrados: {len(historicos)}")
        print(f"{'='*100}")

        # Agrupa por chamado_id para mostrar quantos registros por chamado
        from collections import Counter
        chamado_counts = Counter(h.chamado_id for h in historicos)
        print(f"\nTotal de chamados únicos: {len(chamado_counts)}")
        duplicados = {k: v for k, v in chamado_counts.items() if v > 1}
        print(f"Chamados com múltiplos registros: {len(duplicados)}")

        if duplicados:
            print(f"\nExemplos de chamados com duplicatas:")
            for chamado_id, count in list(duplicados.items())[:5]:
                print(f"  - Chamado #{chamado_id}: {count} registros")

        print(f"\n{'─'*100}")
        print(f"{'Chamado':>8} | {'Aberto':>19} | {'Status':>15} | {'Resposta':>19} | {'Delta (horas)':>14} | {'Validado?':>10}")
        print(f"{'─'*100}")

        # Mostra exemplos detalhados
        for h in historicos[:15]:  # Primeiros 15
            chamado = db.query(Chamado).filter(Chamado.id == h.chamado_id).first()
            if chamado:
                delta = h.data_inicio - chamado.data_abertura if h.data_inicio else None
                horas = delta.total_seconds() / 3600 if delta else 0
                validado = "✓" if (0 <= horas <= 72) else "✗"
                print(f"{h.chamado_id:>8} | {str(chamado.data_abertura):>19} | {h.status:>15} | "
                      f"{str(h.data_inicio):>19} | {horas:>14.1f} | {validado:>10}")

        if len(historicos) > 15:
            print(f"{'─'*100}")
            print(f"... e mais {len(historicos) - 15} registros")

        print(f"{'='*100}\n")

        return historicos

    @staticmethod
    def get_dashboard_metrics(db: Session) -> dict:
        """Retorna todos os métricas do dashboard"""
        try:
            tempo_resposta_mes, total_chamados_mes = MetricsCalculator.get_tempo_medio_resposta_mes(db)

            chamados_hoje = MetricsCalculator.get_chamados_abertos_hoje(db)
            comparacao_ontem = MetricsCalculator.get_comparacao_ontem(db)
            tempo_resposta_24h = MetricsCalculator.get_tempo_medio_resposta_24h(db)
            sla_compliance = MetricsCalculator.get_sla_compliance_mes(db)
            abertos_agora = MetricsCalculator.get_abertos_agora(db)
            tempo_resolucao = MetricsCalculator.get_tempo_resolucao_media_30dias(db)

            return {
                "chamados_hoje": chamados_hoje,
                "comparacao_ontem": comparacao_ontem,
                "tempo_resposta_24h": tempo_resposta_24h,
                "tempo_resposta_mes": tempo_resposta_mes,
                "total_chamados_mes": total_chamados_mes,
                "sla_compliance_24h": sla_compliance,
                "abertos_agora": abertos_agora,
                "tempo_resolucao_30dias": tempo_resolucao,
            }
        except Exception as e:
            print(f"Erro crítico ao calcular métricas do dashboard: {e}")
            import traceback
            traceback.print_exc()
            return {
                "chamados_hoje": 0,
                "comparacao_ontem": {"hoje": 0, "ontem": 0, "percentual": 0, "direcao": "up"},
                "tempo_resposta_24h": "—",
                "tempo_resposta_mes": "—",
                "total_chamados_mes": 0,
                "sla_compliance_24h": 0,
                "abertos_agora": 0,
                "tempo_resolucao_30dias": "—",
            }
