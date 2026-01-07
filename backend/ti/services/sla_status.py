"""
SLA Status System - Define clear, mutually exclusive states

Estados finais (chamado encerrado):
- CUMPRIDO: Fechado dentro do prazo SLA
- VIOLADO: Fechado fora do prazo SLA

Estados ativos (chamado aberto):
- DENTRO_PRAZO: Aberto, tempo consumido < 80% do limite
- PROXIMO_VENCER: Aberto, tempo consumido 80-100% do limite
- VENCIDO_ATIVO: Aberto, tempo consumido > 100% do limite

Estados especiais:
- PAUSADO: Chamado em status "Aguardando Cliente" (não conta tempo)
- SEM_SLA: Sem configuração de SLA para esta prioridade

Regras de transição:
- Uma vez que entra em estado final (CUMPRIDO/VIOLADO), não sai
- PAUSADO pode voltar para estados ativos
- Estados finais são definitivos
"""

from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Session
from ti.models.sla_config import SLAConfiguration
from ti.models.chamado import Chamado
from core.utils import now_brazil_naive


class SLAStatus(str, Enum):
    """Estados de SLA mutuamente exclusivos"""
    # Finais
    CUMPRIDO = "cumprido"
    VIOLADO = "violado"
    
    # Ativos
    DENTRO_PRAZO = "dentro_prazo"
    PROXIMO_VENCER = "proximo_vencer"
    VENCIDO_ATIVO = "vencido_ativo"
    
    # Especiais
    PAUSADO = "pausado"
    SEM_SLA = "sem_sla"


class SLAStatusDeterminer:
    """
    Lógica pura para determinar status de SLA.
    Separada de I/O para ser facilmente testável.
    """
    
    # Status de chamado que indicam pausa
    PAUSED_STATUSES = {"Aguardando", "Aguardando Cliente"}
    
    # Status de chamado que indicam encerramento
    CLOSED_STATUSES = {"Concluído", "Concluido", "Cancelado"}
    
    @staticmethod
    def determine_status(
        chamado_status: str,
        tempo_decorrido_horas: float,
        tempo_limite_horas: float,
        is_closed: bool
    ) -> SLAStatus:
        """
        Determina status de SLA baseado em regras claras.
        
        Args:
            chamado_status: Status atual do chamado
            tempo_decorrido_horas: Tempo já consumido em horas de negócio
            tempo_limite_horas: Limite de tempo para SLA em horas de negócio
            is_closed: Se o chamado está fechado
            
        Returns:
            SLAStatus: Status SLA determinado
        """
        # Pausa (não conta tempo, não viola SLA)
        if chamado_status in SLAStatusDeterminer.PAUSED_STATUSES:
            return SLAStatus.PAUSADO
        
        # Fechado
        if is_closed:
            if tempo_decorrido_horas <= tempo_limite_horas:
                return SLAStatus.CUMPRIDO
            else:
                return SLAStatus.VIOLADO
        
        # Aberto - calcular percentual consumido
        percentual = (tempo_decorrido_horas / tempo_limite_horas * 100) if tempo_limite_horas > 0 else 0
        
        if percentual > 100:
            return SLAStatus.VENCIDO_ATIVO
        elif percentual >= 80:
            return SLAStatus.PROXIMO_VENCER
        else:
            return SLAStatus.DENTRO_PRAZO
    
    @staticmethod
    def get_status_color(status: SLAStatus) -> str:
        """Retorna cor para visualização do status"""
        colors = {
            SLAStatus.CUMPRIDO: "#10b981",      # green
            SLAStatus.VIOLADO: "#ef4444",       # red
            SLAStatus.DENTRO_PRAZO: "#3b82f6",  # blue
            SLAStatus.PROXIMO_VENCER: "#f59e0b", # amber
            SLAStatus.VENCIDO_ATIVO: "#ef4444",  # red
            SLAStatus.PAUSADO: "#6b7280",       # gray
            SLAStatus.SEM_SLA: "#9ca3af",       # gray-400
        }
        return colors.get(status, "#6b7280")
    
    @staticmethod
    def get_status_label_pt(status: SLAStatus) -> str:
        """Retorna label em português para visualização"""
        labels = {
            SLAStatus.CUMPRIDO: "Cumprido",
            SLAStatus.VIOLADO: "Violado",
            SLAStatus.DENTRO_PRAZO: "Dentro do Prazo",
            SLAStatus.PROXIMO_VENCER: "Próximo Vencer",
            SLAStatus.VENCIDO_ATIVO: "Vencido",
            SLAStatus.PAUSADO: "Pausado",
            SLAStatus.SEM_SLA: "Sem SLA",
        }
        return labels.get(status, "Desconhecido")


class SLAResponseMetric:
    """Métrica de resposta SLA"""
    
    def __init__(
        self,
        tempo_decorrido_horas: float,
        tempo_limite_horas: float,
        data_inicio: datetime | None,
        data_fim: datetime | None,
        status: SLAStatus
    ):
        self.tempo_decorrido_horas = tempo_decorrido_horas
        self.tempo_limite_horas = tempo_limite_horas
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.status = status
        self.percentual_consumido = (
            (tempo_decorrido_horas / tempo_limite_horas * 100)
            if tempo_limite_horas > 0 else 0
        )
    
    def is_within_sla(self) -> bool:
        """Verifica se está dentro do SLA"""
        return self.status in {SLAStatus.CUMPRIDO, SLAStatus.DENTRO_PRAZO, SLAStatus.PROXIMO_VENCER, SLAStatus.PAUSADO}
    
    def is_violated(self) -> bool:
        """Verifica se violou o SLA"""
        return self.status in {SLAStatus.VIOLADO, SLAStatus.VENCIDO_ATIVO}


class SLAResolutionMetric:
    """Métrica de resolução SLA"""
    
    def __init__(
        self,
        tempo_decorrido_horas: float,
        tempo_limite_horas: float,
        data_inicio: datetime | None,
        data_fim: datetime | None,
        status: SLAStatus
    ):
        self.tempo_decorrido_horas = tempo_decorrido_horas
        self.tempo_limite_horas = tempo_limite_horas
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.status = status
        self.percentual_consumido = (
            (tempo_decorrido_horas / tempo_limite_horas * 100)
            if tempo_limite_horas > 0 else 0
        )
    
    def is_within_sla(self) -> bool:
        """Verifica se está dentro do SLA"""
        return self.status in {SLAStatus.CUMPRIDO, SLAStatus.DENTRO_PRAZO, SLAStatus.PROXIMO_VENCER, SLAStatus.PAUSADO}
    
    def is_violated(self) -> bool:
        """Verifica se violou o SLA"""
        return self.status in {SLAStatus.VIOLADO, SLAStatus.VENCIDO_ATIVO}
