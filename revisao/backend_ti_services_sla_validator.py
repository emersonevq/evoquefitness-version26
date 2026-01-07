from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from ti.models.sla_config import SLAConfiguration, SLABusinessHours


class SLAValidationError(Exception):
    """Exceção para erros de validação de SLA"""
    pass


class SLAValidator:
    """
    Validador robusto para configurações de SLA.
    Garante que as configurações estão corretas antes de serem usadas em cálculos.
    """

    # Limites aceitáveis (em horas)
    MIN_TEMPO_RESPOSTA = 0.5  # Mínimo 30 minutos
    MAX_TEMPO_RESPOSTA = 72.0  # Máximo 72 horas (3 dias)

    MIN_TEMPO_RESOLUCAO = 1.0  # Mínimo 1 hora
    MAX_TEMPO_RESOLUCAO = 168.0  # Máximo 168 horas (1 semana)

    # Prioridades padrão esperadas
    PRIORIDADES_PADRAO = ["baixa", "média", "alta", "crítica"]

    @staticmethod
    def validar_configuracao(config: SLAConfiguration) -> dict:
        """
        Valida uma configuração de SLA individual.

        Retorna:
            dict com status de validação e lista de warnings/erros
        """
        erros = []
        warnings = []

        # Validação 1: Prioridade não pode ser vazia
        if not config.prioridade or not config.prioridade.strip():
            erros.append("Prioridade não pode estar vazia")

        # Validação 2: Tempo de resposta deve estar dentro dos limites
        if config.tempo_resposta_horas < SLAValidator.MIN_TEMPO_RESPOSTA:
            erros.append(
                f"Tempo de resposta muito baixo ({config.tempo_resposta_horas}h). "
                f"Mínimo: {SLAValidator.MIN_TEMPO_RESPOSTA}h"
            )

        if config.tempo_resposta_horas > SLAValidator.MAX_TEMPO_RESPOSTA:
            erros.append(
                f"Tempo de resposta muito alto ({config.tempo_resposta_horas}h). "
                f"Máximo: {SLAValidator.MAX_TEMPO_RESPOSTA}h"
            )

        # Validação 3: Tempo de resolução deve estar dentro dos limites
        if config.tempo_resolucao_horas < SLAValidator.MIN_TEMPO_RESOLUCAO:
            erros.append(
                f"Tempo de resolução muito baixo ({config.tempo_resolucao_horas}h). "
                f"Mínimo: {SLAValidator.MIN_TEMPO_RESOLUCAO}h"
            )

        if config.tempo_resolucao_horas > SLAValidator.MAX_TEMPO_RESOLUCAO:
            erros.append(
                f"Tempo de resolução muito alto ({config.tempo_resolucao_horas}h). "
                f"Máximo: {SLAValidator.MAX_TEMPO_RESOLUCAO}h"
            )

        # Validação 4: Tempo de resolução deve ser >= tempo de resposta
        if config.tempo_resolucao_horas < config.tempo_resposta_horas:
            erros.append(
                f"Tempo de resolução ({config.tempo_resolucao_horas}h) não pode ser menor que "
                f"tempo de resposta ({config.tempo_resposta_horas}h)"
            )

        # Warning: Prioridade não é padrão
        if config.prioridade.lower() not in SLAValidator.PRIORIDADES_PADRAO:
            warnings.append(
                f"Prioridade '{config.prioridade}' não é uma das padrões "
                f"({', '.join(SLAValidator.PRIORIDADES_PADRAO)})"
            )

        # Warning: Configuração está inativa
        if not config.ativo:
            warnings.append("Esta configuração está inativa e não será usada em cálculos")

        return {
            "valida": len(erros) == 0,
            "erros": erros,
            "warnings": warnings,
        }

    @staticmethod
    def validar_horario_comercial(horas: list[SLABusinessHours]) -> dict:
        """
        Valida configurações de horários comerciais.

        Retorna:
            dict com status de validação e lista de warnings/erros
        """
        erros = []
        warnings = []

        if not horas:
            warnings.append("Nenhum horário comercial configurado, usando padrão (8h-18h seg-sex)")
            return {
                "valida": True,
                "erros": erros,
                "warnings": warnings,
            }

        # Verifica se todos os dias têm configuração
        dias_configurados = {h.dia_semana for h in horas if h.ativo}
        dias_obrigatorios = set(range(5))  # Segunda a sexta (0-4)

        dias_faltando = dias_obrigatorios - dias_configurados
        if dias_faltando:
            dias_nomes = ["segunda", "terça", "quarta", "quinta", "sexta"]
            dias_str = ", ".join(dias_nomes[i] for i in sorted(dias_faltando))
            warnings.append(f"Dias não configurados (usando padrão): {dias_str}")

        # Valida cada horário
        for h in horas:
            if not h.hora_inicio or not h.hora_fim:
                erros.append(f"Dia {h.dia_semana}: horários vazios")
                continue

            try:
                from datetime import datetime

                inicio = datetime.strptime(h.hora_inicio, "%H:%M").time()
                fim = datetime.strptime(h.hora_fim, "%H:%M").time()

                if inicio >= fim:
                    erros.append(
                        f"Dia {h.dia_semana}: hora inicial ({h.hora_inicio}) "
                        f"não pode ser >= hora final ({h.hora_fim})"
                    )

            except ValueError as e:
                erros.append(f"Dia {h.dia_semana}: formato de hora inválido - {str(e)}")

        return {
            "valida": len(erros) == 0,
            "erros": erros,
            "warnings": warnings,
        }

    @staticmethod
    def validar_todas_configuracoes(db: Session) -> dict:
        """
        Valida TODAS as configurações de SLA no banco de dados.
        Deve ser chamado após alterações em configurações.

        Retorna:
            dict com resumo da validação
        """
        configs = db.query(SLAConfiguration).all()
        horas = db.query(SLABusinessHours).all()

        configuracoes_validacoes = []
        for config in configs:
            validacao = SLAValidator.validar_configuracao(config)
            configuracoes_validacoes.append({
                "prioridade": config.prioridade,
                "validacao": validacao,
            })

        horarios_validacao = SLAValidator.validar_horario_comercial(horas)

        # Resumo geral
        todas_validas = all(v["validacao"]["valida"] for v in configuracoes_validacoes)
        total_erros = sum(len(v["validacao"]["erros"]) for v in configuracoes_validacoes)
        total_warnings = sum(len(v["validacao"]["warnings"]) for v in configuracoes_validacoes)
        total_warnings += len(horarios_validacao["warnings"])
        total_erros += len(horarios_validacao["erros"])

        return {
            "sistema_valido": todas_validas and horarios_validacao["valida"],
            "configuracoes": configuracoes_validacoes,
            "horarios_comerciais": horarios_validacao,
            "resumo": {
                "total_configs": len(configs),
                "configs_validas": sum(1 for v in configuracoes_validacoes if v["validacao"]["valida"]),
                "total_erros": total_erros,
                "total_warnings": total_warnings,
            },
        }

    @staticmethod
    def validar_dados_chamado(db: Session, chamado_id: int) -> dict:
        """
        Valida dados de um chamado específico para cálculo de SLA.
        Útil para debug de cálculos incorretos.

        Retorna:
            dict com dados de validação do chamado
        """
        from ti.models.chamado import Chamado
        from ti.models.historico_status import HistoricoStatus

        chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()

        if not chamado:
            raise SLAValidationError(f"Chamado {chamado_id} não encontrado")

        # Valida configuração de SLA para prioridade
        config = db.query(SLAConfiguration).filter(
            SLAConfiguration.prioridade == chamado.prioridade
        ).first()

        if not config:
            return {
                "chamado_id": chamado_id,
                "prioridade": chamado.prioridade,
                "erro": f"Nenhuma configuração de SLA para prioridade '{chamado.prioridade}'",
                "config_existe": False,
            }

        # Valida datas
        dados_validacao = {
            "chamado_id": chamado_id,
            "prioridade": chamado.prioridade,
            "status": chamado.status,
            "config_existe": True,
            "datas": {
                "data_abertura": chamado.data_abertura.isoformat() if chamado.data_abertura else None,
                "data_primeira_resposta": chamado.data_primeira_resposta.isoformat() if chamado.data_primeira_resposta else None,
                "data_conclusao": chamado.data_conclusao.isoformat() if chamado.data_conclusao else None,
            },
            "datas_validas": True,
            "datas_warnings": [],
        }

        # Validações de sequência de datas
        if chamado.data_abertura and chamado.data_primeira_resposta:
            if chamado.data_primeira_resposta < chamado.data_abertura:
                dados_validacao["datas_validas"] = False
                dados_validacao["datas_warnings"].append(
                    "Data de primeira resposta anterior à data de abertura"
                )

        if chamado.data_abertura and chamado.data_conclusao:
            if chamado.data_conclusao < chamado.data_abertura:
                dados_validacao["datas_validas"] = False
                dados_validacao["datas_warnings"].append(
                    "Data de conclusão anterior à data de abertura"
                )

        if chamado.data_primeira_resposta and chamado.data_conclusao:
            if chamado.data_conclusao < chamado.data_primeira_resposta:
                dados_validacao["datas_validas"] = False
                dados_validacao["datas_warnings"].append(
                    "Data de conclusão anterior à data de primeira resposta"
                )

        # Conta históricos
        historicos_count = db.query(HistoricoStatus).filter(
            HistoricoStatus.chamado_id == chamado_id
        ).count()

        dados_validacao["historicos_count"] = historicos_count

        return dados_validacao
