from __future__ import annotations
from datetime import datetime, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ti.models.sla_config import SLAConfiguration, SLABusinessHours, HistoricoSLA
from ti.models.historico_status import HistoricoStatus
from ti.models.chamado import Chamado
from core.utils import now_brazil_naive


class SLACalculator:
    DEFAULT_BUSINESS_HOURS = {
        0: ("08:00", "18:00"),
        1: ("08:00", "18:00"),
        2: ("08:00", "18:00"),
        3: ("08:00", "18:00"),
        4: ("08:00", "18:00"),
    }

    @staticmethod
    def get_business_hours(db: Session, dia_semana: int) -> tuple[str, str] | None:
        try:
            bh = db.query(SLABusinessHours).filter(
                and_(
                    SLABusinessHours.dia_semana == dia_semana,
                    SLABusinessHours.ativo == True
                )
            ).first()
            if bh:
                return (bh.hora_inicio, bh.hora_fim)
        except Exception:
            pass
        return SLACalculator.DEFAULT_BUSINESS_HOURS.get(dia_semana)

    @staticmethod
    def is_business_day(data: datetime) -> bool:
        return data.weekday() < 5

    @staticmethod
    def is_business_time(dt: datetime, db: Session | None = None) -> bool:
        if not SLACalculator.is_business_day(dt):
            return False

        bh = None
        if db:
            bh = SLACalculator.get_business_hours(db, dt.weekday())
        else:
            bh = SLACalculator.DEFAULT_BUSINESS_HOURS.get(dt.weekday())

        if not bh:
            return False

        hora_inicio = datetime.strptime(bh[0], "%H:%M").time()
        hora_fim = datetime.strptime(bh[1], "%H:%M").time()
        return hora_inicio <= dt.time() <= hora_fim

    @staticmethod
    def calculate_business_hours_excluding_paused(
        chamado_id: int,
        start: datetime,
        end: datetime,
        db: Session,
        historicos_cache: dict | None = None
    ) -> float:
        """
        Calcula horas de NEGÓCIO excluindo períodos em "Em análise".

        Lógica:
        1. Calcula horas de negócio total (start até end)
        2. Identifica períodos onde status = "Em análise"
        3. Subtrai horas em "Em análise" do total

        Parâmetro historicos_cache: dict {chamado_id: [historicos]}
        Se fornecido, evita queries ao banco (otimização para bulk)

        Retorna: horas de negócio SEM contar pausa
        """
        if start >= end:
            return 0.0

        # 1. Calcula tempo total em horas de negócio
        tempo_total = SLACalculator.calculate_business_hours(start, end, db)

        # 2. Busca períodos em "Em análise"
        from ti.models.historico_status import HistoricoStatus

        if historicos_cache and chamado_id in historicos_cache:
            # Usa cache se disponível (bulk operation)
            historicos_analise = [
                h for h in historicos_cache[chamado_id]
                if h.status.lower() in ["em análise", "em analise"]
                and h.data_inicio and h.data_fim
                and h.data_inicio >= start
                and h.data_fim <= end
            ]
        else:
            # Query ao banco (operação individual)
            historicos_analise = db.query(HistoricoStatus).filter(
                and_(
                    HistoricoStatus.chamado_id == chamado_id,
                    HistoricoStatus.status.in_(["Em análise", "Em Análise"]),
                    HistoricoStatus.data_inicio.isnot(None),
                    HistoricoStatus.data_fim.isnot(None),
                    HistoricoStatus.data_inicio >= start,
                    HistoricoStatus.data_fim <= end,
                )
            ).all()

        # 3. Subtrai horas em "Em análise"
        tempo_analise_total = 0.0
        for hist in historicos_analise:
            if hist.data_inicio and hist.data_fim:
                tempo_analise = SLACalculator.calculate_business_hours(
                    hist.data_inicio,
                    hist.data_fim,
                    db
                )
                tempo_analise_total += tempo_analise

        # Retorna tempo total menos pausa
        tempo_sla = tempo_total - tempo_analise_total
        return max(0, tempo_sla)  # Nunca negativo

    @staticmethod
    def calculate_business_hours(start: datetime, end: datetime, db: Session | None = None) -> float:
        if start >= end:
            return 0.0

        total_minutes = 0
        current = start

        while current < end:
            next_day = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            if not SLACalculator.is_business_day(current):
                current = next_day
                continue

            bh = None
            if db:
                bh = SLACalculator.get_business_hours(db, current.weekday())
            else:
                bh = SLACalculator.DEFAULT_BUSINESS_HOURS.get(current.weekday())

            if not bh:
                current = next_day
                continue

            hora_inicio = datetime.strptime(bh[0], "%H:%M").time()
            hora_fim = datetime.strptime(bh[1], "%H:%M").time()

            day_start = current.replace(hour=hora_inicio.hour, minute=hora_inicio.minute, second=0, microsecond=0)
            day_end = current.replace(hour=hora_fim.hour, minute=hora_fim.minute, second=0, microsecond=0)

            if current < day_start:
                current = day_start

            if end <= day_end:
                total_minutes += int((end - current).total_seconds() / 60)
                break
            else:
                total_minutes += int((day_end - current).total_seconds() / 60)
                current = next_day

        return total_minutes / 60.0

    @staticmethod
    def get_sla_config_by_priority(db: Session, prioridade: str) -> SLAConfiguration | None:
        try:
            return db.query(SLAConfiguration).filter(
                and_(
                    SLAConfiguration.prioridade == prioridade,
                    SLAConfiguration.ativo == True
                )
            ).first()
        except Exception:
            return None

    @staticmethod
    def get_first_response_date(db: Session, chamado_id: int) -> datetime | None:
        """
        Obtém a data da primeira resposta (primeira transição para 'Em Atendimento' ou 'Em análise').
        Procura no histórico de status.
        """
        try:
            historico = db.query(HistoricoStatus).filter(
                and_(
                    HistoricoStatus.chamado_id == chamado_id,
                    HistoricoStatus.status.in_(["Em Atendimento", "Em análise", "Em andamento"])
                )
            ).order_by(HistoricoStatus.data_inicio.asc()).first()

            if historico and historico.data_inicio:
                return historico.data_inicio
        except Exception:
            pass
        return None

    @staticmethod
    def get_completion_date(db: Session, chamado_id: int) -> datetime | None:
        """
        Obtém a data de conclusão (primeira transição para 'Concluído').
        Procura no histórico de status.
        """
        try:
            historico = db.query(HistoricoStatus).filter(
                and_(
                    HistoricoStatus.chamado_id == chamado_id,
                    HistoricoStatus.status.in_(["Concluído", "Concluido"])
                )
            ).order_by(HistoricoStatus.data_inicio.asc()).first()

            if historico and historico.data_inicio:
                return historico.data_inicio
        except Exception:
            pass
        return None

    @staticmethod
    def is_frozen(db: Session, chamado_id: int, agora: datetime | None = None) -> bool:
        """
        Verifica se o chamado está congelado (parado em 'Aguardando' ou 'Em análise').
        Um chamado é considerado congelado se o último status é 'Aguardando' ou 'Em análise'.
        """
        if agora is None:
            agora = now_brazil_naive()

        try:
            # Pega o último status registrado
            ultimo_status = db.query(HistoricoStatus).filter(
                HistoricoStatus.chamado_id == chamado_id
            ).order_by(HistoricoStatus.data_inicio.desc()).first()

            if not ultimo_status:
                return False

            # Verifica se o último status é "Aguardando" ou "Em análise"
            status_atual = ultimo_status.status or ""
            if status_atual not in ["Aguardando", "Em análise"]:
                return False

            return True

        except Exception:
            pass

        return False

    @staticmethod
    def get_sla_status(db: Session, chamado: Chamado) -> dict:
        """
        Calcula o status de SLA de um chamado com estados claros e mutuamente exclusivos.

        Usa:
        - Chamado.data_primeira_resposta para data de primeira resposta (fonte confiável)
        - Chamado.data_conclusao para data de conclusão
        - Histórico de status para verificar se está pausado

        Retorna status com novo sistema de estados.
        """
        from ti.services.sla_status import SLAStatus, SLAStatusDeterminer, SLAResponseMetric, SLAResolutionMetric

        sla_config = SLACalculator.get_sla_config_by_priority(db, chamado.prioridade)

        if not sla_config:
            return {
                "chamado_id": chamado.id,
                "prioridade": chamado.prioridade,
                "status_chamado": chamado.status,
                "resposta_metric": None,
                "resolucao_metric": None,
                "status_geral": SLAStatus.SEM_SLA.value,
                "data_abertura": chamado.data_abertura,
                "data_primeira_resposta": None,
                "data_conclusao": None,
            }

        data_abertura = chamado.data_abertura
        if not data_abertura:
            data_abertura = now_brazil_naive()
        agora = now_brazil_naive()
        is_closed = chamado.status in SLAStatusDeterminer.CLOSED_STATUSES

        # ===== MÉTRICA DE RESPOSTA (SLA de Resposta) =====
        tempo_resposta_horas = 0
        data_primeira_resposta = chamado.data_primeira_resposta
        resposta_metric = None

        if data_primeira_resposta:
            # Já houve resposta
            tempo_resposta_horas = SLACalculator.calculate_business_hours(
                data_abertura, data_primeira_resposta, db
            )
        elif chamado.status not in SLAStatusDeterminer.CLOSED_STATUSES:
            # Ainda não respondeu, calcular até agora
            tempo_resposta_horas = SLACalculator.calculate_business_hours(
                data_abertura, agora, db
            )

        resposta_status = SLAStatusDeterminer.determine_status(
            chamado.status,
            tempo_resposta_horas,
            sla_config.tempo_resposta_horas,
            is_closed and data_primeira_resposta is None
        )

        resposta_metric = SLAResponseMetric(
            tempo_decorrido_horas=tempo_resposta_horas,
            tempo_limite_horas=sla_config.tempo_resposta_horas,
            data_inicio=data_abertura,
            data_fim=data_primeira_resposta,
            status=resposta_status
        )

        # ===== MÉTRICA DE RESOLUÇÃO (SLA de Resolução) =====
        tempo_resolucao_horas = 0
        data_conclusao = chamado.data_conclusao
        resolucao_metric = None

        # Desconta tempo em "Em análise" para chamados não pausados
        if chamado.status not in SLAStatusDeterminer.PAUSED_STATUSES:
            data_final = data_conclusao if data_conclusao else agora
            tempo_resolucao_horas = SLACalculator.calculate_business_hours_excluding_paused(
                chamado.id, data_abertura, data_final, db
            )
        else:
            # Pausado: não conta tempo desde abertura até agora
            tempo_resolucao_horas = SLACalculator.calculate_business_hours_excluding_paused(
                chamado.id, data_abertura, agora, db
            )

        resolucao_status = SLAStatusDeterminer.determine_status(
            chamado.status,
            tempo_resolucao_horas,
            sla_config.tempo_resolucao_horas,
            is_closed
        )

        resolucao_metric = SLAResolutionMetric(
            tempo_decorrido_horas=tempo_resolucao_horas,
            tempo_limite_horas=sla_config.tempo_resolucao_horas,
            data_inicio=data_abertura,
            data_fim=data_conclusao,
            status=resolucao_status
        )

        # Status geral: o mais crítico dos dois
        status_geral = resolucao_status  # Resolução é mais crítica que resposta

        return {
            "chamado_id": chamado.id,
            "prioridade": chamado.prioridade,
            "status_chamado": chamado.status,
            "resposta_metric": {
                "tempo_decorrido_horas": resposta_metric.tempo_decorrido_horas,
                "tempo_limite_horas": resposta_metric.tempo_limite_horas,
                "percentual_consumido": resposta_metric.percentual_consumido,
                "status": resposta_metric.status.value,
                "data_inicio": data_abertura,
                "data_fim": data_primeira_resposta,
            },
            "resolucao_metric": {
                "tempo_decorrido_horas": resolucao_metric.tempo_decorrido_horas,
                "tempo_limite_horas": resolucao_metric.tempo_limite_horas,
                "percentual_consumido": resolucao_metric.percentual_consumido,
                "status": resolucao_metric.status.value,
                "data_inicio": data_abertura,
                "data_fim": data_conclusao,
            },
            "status_geral": status_geral.value,
            "data_abertura": chamado.data_abertura,
            "data_primeira_resposta": data_primeira_resposta,
            "data_conclusao": data_conclusao,
        }

    @staticmethod
    def record_sla_history(
        db: Session,
        chamado_id: int,
        usuario_id: int | None,
        acao: str,
        status_anterior: str | None = None,
        status_novo: str | None = None,
        tempo_resolucao_horas: float | None = None,
        limite_sla_horas: float | None = None,
        status_sla: str | None = None,
    ) -> HistoricoSLA:
        try:
            historico = HistoricoSLA(
                chamado_id=chamado_id,
                usuario_id=usuario_id,
                acao=acao,
                status_anterior=status_anterior,
                status_novo=status_novo,
                tempo_resolucao_horas=tempo_resolucao_horas,
                limite_sla_horas=limite_sla_horas,
                status_sla=status_sla,
                criado_em=now_brazil_naive(),
            )
            db.add(historico)
            db.commit()
            db.refresh(historico)
            return historico
        except Exception as e:
            db.rollback()
            raise e
