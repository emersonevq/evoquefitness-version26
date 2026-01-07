"""
Sistema de agendamento para recalcular SLA automaticamente.

Características:
- Roda automaticamente todos os dias às 00:00 (horário de Brasília)
- Atualiza cache de métricas
- Registra logs de execução
- Thread-safe

Uso:
    from ti.services.sla_scheduler import SLAScheduler
    
    # Inicializa o scheduler na startup da aplicação
    scheduler = SLAScheduler()
    scheduler.start()
"""

import threading
import logging
from datetime import datetime, time
from sqlalchemy.orm import Session

from core.db import SessionLocal
from core.utils import now_brazil_naive
from ti.services.sla_cache import SLACacheManager
from ti.services.metrics import MetricsCalculator

logger = logging.getLogger(__name__)


class SLAScheduler:
    """Agendador de recalculação de SLA"""

    # Horário para executar (00:00 horário de Brasília)
    SCHEDULED_TIME = time(0, 0, 0)

    def __init__(self):
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def start(self):
        """Inicia o scheduler em thread separada"""
        with self.lock:
            if self.running:
                logger.warning("SLA Scheduler já está em execução")
                return

            self.running = True
            self.thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True,
                name="SLASchedulerThread"
            )
            self.thread.start()
            logger.info("SLA Scheduler iniciado")

    def stop(self):
        """Para o scheduler"""
        with self.lock:
            self.running = False
        logger.info("SLA Scheduler parado")

    def _scheduler_loop(self):
        """Loop principal do scheduler"""
        import time

        last_execution_date = None

        while self.running:
            try:
                agora = now_brazil_naive()

                # Verifica se é um novo dia
                if last_execution_date != agora.date():
                    # Verifica se chegou no horário agendado
                    if agora.time() >= self.SCHEDULED_TIME:
                        # Executa uma vez por dia
                        if last_execution_date is None or last_execution_date < agora.date():
                            logger.info(f"🔄 Iniciando recalculação automática de SLA em {agora}")
                            self._recalculate_sla()
                            last_execution_date = agora.date()

                # Dorme por 1 minuto antes de verificar novamente
                time.sleep(60)

            except Exception as e:
                logger.error(f"Erro no scheduler de SLA: {e}", exc_info=True)
                # Continua mesmo com erro
                import time
                time.sleep(60)

    def _recalculate_sla(self):
        """Executa o recálculo de SLA"""
        db = SessionLocal()
        try:
            from ti.scripts.recalculate_sla_complete import SLARecalculator

            recalculator = SLARecalculator(db)
            stats = recalculator.recalculate_all(verbose=False)

            # Log dos resultados
            logger.info(
                f"✅ Recalculação de SLA concluída: "
                f"{stats['recalculados']} recalculados, "
                f"{stats['com_erro']} com erro. "
                f"Tempo médio de resposta: {stats['tempo_medio_resposta_horas']:.2f}h, "
                f"Tempo médio de resolução: {stats['tempo_medio_resolucao_horas']:.2f}h"
            )

            # Também aquece o cache com as métricas principais
            self._warmup_cache(db)

            db.commit()

        except Exception as e:
            logger.error(f"Erro durante recalculação automática de SLA: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _warmup_cache(self, db: Session):
        """Pré-aquece o cache com métricas principais"""
        try:
            # Calcula e cacheia as métricas principais
            MetricsCalculator.get_sla_compliance_24h(db)
            MetricsCalculator.get_sla_compliance_mes(db)
            MetricsCalculator.get_sla_distribution(db)
            MetricsCalculator.get_tempo_medio_resposta_24h(db)
            MetricsCalculator.get_tempo_medio_resposta_mes(db)

            logger.debug("✅ Cache aquecido com métricas principais")
        except Exception as e:
            logger.warning(f"Erro ao aquecer cache: {e}")


# Instância global singleton
_scheduler_instance = None


def get_scheduler() -> SLAScheduler:
    """Obtém a instância global do scheduler"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SLAScheduler()
    return _scheduler_instance


def init_scheduler():
    """Inicializa o scheduler na startup da aplicação"""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler
