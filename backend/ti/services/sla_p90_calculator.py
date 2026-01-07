from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ti.models.chamado import Chamado
from ti.models.historico_status import HistoricoStatus
from ti.models.sla_config import SLAConfiguration
from ti.services.sla import SLACalculator
from core.utils import now_brazil_naive
import statistics


class SLAP90Calculator:
    """Calcula SLA baseado em P90 (90º percentil) dos últimos 30 dias"""

    @staticmethod
    def calcular_percentil_90(valores: list[float]) -> float:
        """
        Calcula o 90º percentil de uma lista de valores.
        
        P90 significa que 90% dos valores estão abaixo deste número.
        """
        if not valores or len(valores) < 2:
            return 0.0
        
        valores_ordenados = sorted(valores)
        indice = int(0.9 * (len(valores_ordenados) - 1))
        
        if indice >= len(valores_ordenados):
            indice = len(valores_ordenados) - 1
        
        return float(valores_ordenados[indice])

    @staticmethod
    def obter_tempo_primeira_resposta(chamado: Chamado, db: Session) -> float:
        """
        Obtém o tempo de primeira resposta em horas.
        
        Primeira resposta = tempo de abertura até a primeira mudança de status
        (excluindo "Em análise" que fica em pausa).
        
        Retorna: horas (float)
        """
        if not chamado.data_abertura:
            return 0.0

        historicos = db.query(HistoricoStatus).filter(
            HistoricoStatus.chamado_id == chamado.id
        ).order_by(HistoricoStatus.data_inicio.asc()).all()

        if not historicos or not historicos[0].data_inicio:
            return 0.0

        primeira_mudanca = historicos[0].data_inicio
        
        tempo_horas = SLACalculator.calculate_business_hours_excluding_paused(
            chamado.id,
            chamado.data_abertura,
            primeira_mudanca,
            db
        )
        
        return tempo_horas

    @staticmethod
    def obter_tempo_resolucao(chamado: Chamado, db: Session) -> float:
        """
        Obtém o tempo de resolução em horas.
        
        Resolução = tempo de abertura até concluído/cancelado
        (excluindo "Em análise" que fica em pausa).
        
        Retorna: horas (float)
        """
        if not chamado.data_abertura:
            return 0.0

        data_conclusao = chamado.data_conclusao or chamado.cancelado_em
        if not data_conclusao:
            return 0.0

        tempo_horas = SLACalculator.calculate_business_hours_excluding_paused(
            chamado.id,
            chamado.data_abertura,
            data_conclusao,
            db
        )
        
        return tempo_horas

    @staticmethod
    def recalcular_sla_por_prioridade(db: Session) -> dict:
        """
        Recalcula SLA para cada prioridade baseado em P90 dos últimos 30 dias.
        
        Processo:
        1. Busca chamados dos últimos 30 dias (status concluído/cancelado)
        2. Agrupa por prioridade
        3. Calcula P90 para tempo de resposta e resolução
        4. Atualiza configurações de SLA
        5. Invalida cache
        """
        agora = now_brazil_naive()
        data_inicio = agora - timedelta(days=30)
        
        print(f"[P90] Iniciando recálculo de SLA de {data_inicio} a {agora}")

        chamados = db.query(Chamado).filter(
            and_(
                Chamado.data_abertura >= data_inicio,
                Chamado.data_abertura <= agora,
                Chamado.deletado_em.is_(None),
                Chamado.status.in_(["Concluído", "Cancelado"])
            )
        ).all()

        print(f"[P90] Encontrados {len(chamados)} chamados nos últimos 30 dias")

        dados_por_prioridade = {}
        
        for chamado in chamados:
            prioridade = chamado.prioridade or "Normal"
            
            if prioridade not in dados_por_prioridade:
                dados_por_prioridade[prioridade] = {
                    "tempos_resposta": [],
                    "tempos_resolucao": [],
                    "total": 0
                }

            tempo_resposta = SLAP90Calculator.obter_tempo_primeira_resposta(chamado, db)
            tempo_resolucao = SLAP90Calculator.obter_tempo_resolucao(chamado, db)

            dados_por_prioridade[prioridade]["tempos_resposta"].append(tempo_resposta)
            dados_por_prioridade[prioridade]["tempos_resolucao"].append(tempo_resolucao)
            dados_por_prioridade[prioridade]["total"] += 1

        resultado = {
            "sucesso": True,
            "data_inicio": data_inicio.isoformat(),
            "data_fim": agora.isoformat(),
            "total_chamados": len(chamados),
            "prioridades_atualizadas": [],
            "detalhes": {}
        }

        for prioridade, dados in dados_por_prioridade.items():
            try:
                tempos_resposta = dados["tempos_resposta"]
                tempos_resolucao = dados["tempos_resolucao"]
                total = dados["total"]

                if not tempos_resposta or not tempos_resolucao:
                    continue

                p90_resposta = SLAP90Calculator.calcular_percentil_90(tempos_resposta)
                p90_resolucao = SLAP90Calculator.calcular_percentil_90(tempos_resolucao)

                margem_seguranca = 1.15
                tempo_resposta_final = p90_resposta * margem_seguranca
                tempo_resolucao_final = p90_resolucao * margem_seguranca

                tempo_resposta_horas = round(tempo_resposta_final)
                tempo_resolucao_horas = round(tempo_resolucao_final)

                config = db.query(SLAConfiguration).filter(
                    SLAConfiguration.prioridade == prioridade
                ).first()

                if not config:
                    print(f"[P90] Prioridade '{prioridade}' não tem configuração, pulando")
                    continue

                print(f"[P90] {prioridade}:")
                print(f"  - Total: {total} chamados")
                print(f"  - P90 Resposta: {p90_resposta:.2f}h → {tempo_resposta_horas}h (com margem)")
                print(f"  - P90 Resolução: {p90_resolucao:.2f}h → {tempo_resolucao_horas}h (com margem)")

                config.tempo_resposta_horas = tempo_resposta_horas
                config.tempo_resolucao_horas = tempo_resolucao_horas
                config.atualizado_em = agora

                db.add(config)

                resultado["detalhes"][prioridade] = {
                    "total_chamados": total,
                    "p90_resposta_horas": round(p90_resposta, 2),
                    "p90_resolucao_horas": round(p90_resolucao, 2),
                    "tempo_resposta_novo": tempo_resposta_horas,
                    "tempo_resolucao_novo": tempo_resolucao_horas,
                    "margem_seguranca": margem_seguranca
                }
                resultado["prioridades_atualizadas"].append(prioridade)

            except Exception as e:
                print(f"[P90] Erro ao processar prioridade '{prioridade}': {e}")
                resultado["detalhes"][prioridade] = {
                    "erro": str(e)
                }

        db.commit()

        from ti.services.sla_cache import SLACacheManager
        SLACacheManager.invalidate_all_sla(db)

        print(f"[P90] Recálculo concluído. Atualizadas {len(resultado['prioridades_atualizadas'])} prioridades")

        return resultado
