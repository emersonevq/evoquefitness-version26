from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class SLAStatusEnum(str, Enum):
    """Estados de SLA mutuamente exclusivos"""
    CUMPRIDO = "cumprido"
    VIOLADO = "violado"
    DENTRO_PRAZO = "dentro_prazo"
    PROXIMO_VENCER = "proximo_vencer"
    VENCIDO_ATIVO = "vencido_ativo"
    PAUSADO = "pausado"
    SEM_SLA = "sem_sla"


class SLAConfigurationCreate(BaseModel):
    prioridade: str = Field(..., description="Nível de prioridade")
    tempo_resposta_horas: float = Field(..., gt=0, description="Tempo máximo de resposta em horas (deve ser positivo)")
    tempo_resolucao_horas: float = Field(..., gt=0, description="Tempo máximo de resolução em horas (deve ser positivo)")
    descricao: str | None = Field(None, description="Descrição da configuração")
    ativo: bool = Field(True, description="Se a configuração está ativa")

    @validator("tempo_resposta_horas", "tempo_resolucao_horas")
    def validate_positive_hours(cls, v):
        if v <= 0:
            raise ValueError("Tempo deve ser maior que zero")
        return v

    @validator("tempo_resolucao_horas")
    def validate_resolucao_maior_que_resposta(cls, v, values):
        if "tempo_resposta_horas" in values:
            if v < values["tempo_resposta_horas"]:
                raise ValueError("Tempo de resolução deve ser >= tempo de resposta")
        return v


class SLAConfigurationUpdate(BaseModel):
    tempo_resposta_horas: float | None = Field(None, gt=0, description="Tempo máximo de resposta em horas")
    tempo_resolucao_horas: float | None = Field(None, gt=0, description="Tempo máximo de resolução em horas")
    descricao: str | None = Field(None, description="Descrição da configuração")
    ativo: bool | None = Field(None, description="Se a configuração está ativa")

    @validator("tempo_resposta_horas", "tempo_resolucao_horas", pre=True, always=True)
    def validate_positive_hours(cls, v):
        """Valida que tempos são positivos quando fornecidos"""
        if v is not None and v <= 0:
            raise ValueError("Tempo deve ser maior que zero")
        return v

    @validator("tempo_resolucao_horas", pre=True, always=True)
    def validate_resolucao_maior_que_resposta(cls, v, values):
        """Valida que resolução >= resposta quando ambas são fornecidas"""
        if v is not None and "tempo_resposta_horas" in values and values["tempo_resposta_horas"] is not None:
            if v < values["tempo_resposta_horas"]:
                raise ValueError("Tempo de resolução deve ser >= tempo de resposta")
        return v


class SLAConfigurationOut(BaseModel):
    id: int
    prioridade: str
    tempo_resposta_horas: float
    tempo_resolucao_horas: float
    descricao: str | None
    ativo: bool
    criado_em: datetime | None
    atualizado_em: datetime | None

    class Config:
        from_attributes = True


class SLABusinessHoursCreate(BaseModel):
    dia_semana: int = Field(..., ge=0, le=6, description="Dia da semana (0=segunda a 4=sexta, 5=sábado, 6=domingo)")
    hora_inicio: str = Field(..., description="Hora de início (HH:MM, ex: 08:00)")
    hora_fim: str = Field(..., description="Hora de término (HH:MM, ex: 18:00)")
    ativo: bool = Field(True, description="Se o horário está ativo")

    @validator("dia_semana")
    def validate_dia_semana(cls, v):
        """Valida dia da semana"""
        if not isinstance(v, int):
            raise ValueError("dia_semana deve ser um inteiro")
        if v < 0 or v > 6:
            raise ValueError("dia_semana deve estar entre 0 (segunda) e 6 (domingo)")
        return v

    @validator("hora_inicio", "hora_fim")
    def validate_time_format(cls, v):
        """Valida formato HH:MM"""
        if not isinstance(v, str):
            raise ValueError("Horário deve ser string no formato HH:MM")
        try:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError()
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError()
        except (ValueError, AttributeError, IndexError):
            raise ValueError(f"Formato inválido '{v}'. Use HH:MM (00:00 a 23:59)")
        return v

    @validator("hora_fim")
    def validate_hora_fim_after_inicio(cls, v, values):
        """Valida que hora_fim é maior que hora_inicio"""
        if "hora_inicio" in values:
            hora_inicio = values["hora_inicio"]
            if v <= hora_inicio:
                raise ValueError("Hora fim deve ser maior que hora início")
        return v


class SLABusinessHoursUpdate(BaseModel):
    """Schema para atualização parcial de horários comerciais"""
    dia_semana: int | None = Field(None, ge=0, le=6, description="Dia da semana")
    hora_inicio: str | None = Field(None, description="Hora de início (HH:MM)")
    hora_fim: str | None = Field(None, description="Hora de término (HH:MM)")
    ativo: bool | None = Field(None, description="Se o horário está ativo")

    @validator("hora_inicio", "hora_fim", pre=True)
    def validate_time_format_optional(cls, v):
        """Valida formato HH:MM quando fornecido"""
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Horário deve ser string no formato HH:MM")
        try:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError()
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError()
        except (ValueError, AttributeError, IndexError):
            raise ValueError(f"Formato inválido '{v}'. Use HH:MM (00:00 a 23:59)")
        return v

    @validator("hora_fim")
    def validate_hora_fim_after_inicio_update(cls, v, values):
        """Valida que hora_fim é maior que hora_inicio quando ambas são fornecidas"""
        if v is not None and "hora_inicio" in values and values["hora_inicio"] is not None:
            if v <= values["hora_inicio"]:
                raise ValueError("Hora fim deve ser maior que hora início")
        return v


class SLABusinessHoursOut(BaseModel):
    id: int
    dia_semana: int
    hora_inicio: str
    hora_fim: str
    ativo: bool
    criado_em: datetime | None
    atualizado_em: datetime | None

    class Config:
        from_attributes = True


class HistoricoSLAOut(BaseModel):
    id: int
    chamado_id: int
    usuario_id: int | None
    acao: str
    status_anterior: str | None
    status_novo: str | None
    data_conclusao_anterior: datetime | None
    data_conclusao_nova: datetime | None
    tempo_resposta_horas: float | None
    limite_sla_resposta_horas: float | None
    tempo_resolucao_horas: float | None
    limite_sla_horas: float | None
    status_sla: str | None
    criado_em: datetime | None

    class Config:
        from_attributes = True


class SLAMetricResponse(BaseModel):
    """Métrica de SLA (resposta ou resolução)"""
    tempo_decorrido_horas: float
    tempo_limite_horas: float
    percentual_consumido: float
    status: str
    data_inicio: datetime | None
    data_fim: datetime | None


class SLAStatusResponse(BaseModel):
    """Resposta completa de status SLA com estados claros"""
    chamado_id: int
    prioridade: str
    status_chamado: str
    resposta_metric: SLAMetricResponse | None
    resolucao_metric: SLAMetricResponse | None
    status_geral: str
    data_abertura: datetime | None
    data_primeira_resposta: datetime | None
    data_conclusao: datetime | None

    class Config:
        from_attributes = True


class SLAFeriadoCreate(BaseModel):
    """Schema para criar feriado"""
    data: str = Field(..., description="Data do feriado (YYYY-MM-DD)")
    nome: str = Field(..., description="Nome do feriado")
    descricao: str | None = Field(None, description="Descrição do feriado")
    ativo: bool = Field(True, description="Se o feriado está ativo")

    @validator("data")
    def validate_data_format(cls, v):
        """Valida formato de data YYYY-MM-DD"""
        from datetime import datetime
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Data deve estar no formato YYYY-MM-DD")
        return v

    @validator("nome")
    def validate_nome_length(cls, v):
        """Valida comprimento do nome"""
        if not v or len(v.strip()) < 3:
            raise ValueError("Nome deve ter pelo menos 3 caracteres")
        return v.strip()


class SLAFeriadoUpdate(BaseModel):
    """Schema para atualizar feriado"""
    nome: str | None = Field(None, description="Nome do feriado")
    descricao: str | None = Field(None, description="Descrição do feriado")
    ativo: bool | None = Field(None, description="Se o feriado está ativo")

    @validator("nome")
    def validate_nome_length(cls, v):
        """Valida comprimento do nome quando fornecido"""
        if v is not None:
            if not v or len(v.strip()) < 3:
                raise ValueError("Nome deve ter pelo menos 3 caracteres")
            return v.strip()
        return v


class SLAFeriadoOut(BaseModel):
    """Schema de saída para feriado"""
    id: int
    data: str
    nome: str
    descricao: str | None
    ativo: bool
    criado_em: datetime | None
    atualizado_em: datetime | None

    class Config:
        from_attributes = True
