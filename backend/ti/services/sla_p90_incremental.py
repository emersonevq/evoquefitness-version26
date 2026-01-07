from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ti.models.chamado import Chamado
from ti.models.historico_status import HistoricoStatus
from ti.models.sla_config import SLAConfiguration
from ti.models.metrics_cache import MetricsCacheDB
from ti.services.sla import SLACalculator
from ti.services.sla_cache import SLACacheManager
from core.utils import now_brazil_naive
import json


class SLAP90Incremental:
    """
    Sistema incremental de cálculo de SLA com P90.
    
    Funciona armazenando em cache:
    1. Lista de tempos já processados
    2. ID do último chamado processado
    
    Na próxima atualização, busca apenas chamados novos.
    """

    CACHE_KEY_TEMPOS_RESPOSTA = "sla_p90_tempos_resposta"
    CACHE_KEY_TEMPOS_RESOLUCAO = "sla_p90_tempos_resolucao"
    CACHE_KEY_ULTIMO_ID = "sla_p90_ultimo_chamado_id"
    CACHE_KEY_TIMESTAMP = "sla_p90_timestamp"

    @staticmethod
    def calcular_percentil_90(valores: list[float]) -> float:
        """Calcula o 90º percentil de uma lista de valores."""
        if not valores or len(valores) < 2:
            return 0.0
        
        valores_ordenados = sorted(valores)
        indice = int(0.9 * (len(valores_ordenados) - 1))
        
        if indice >= len(valores_ordenados):
            indice = len(valores_ordenados) - 1
        
        return float(valores_ordenados[indice])

    @staticmethod
    def obter_tempo_primeira_resposta(chamado: Chamado, db: Session) -> float:
        """Obtém tempo de primeira resposta em horas."""
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
        """Obtém tempo de resolução em horas."""
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
    def carregar_cache_prioridade(db: Session, prioridade: str) -> dict:
        """
        Carrega dados do cache para uma prioridade.
        Retorna dict com tempos anteriores e último ID processado.
        """
        cache_key_resposta = f"{SLAP90Incremental.CACHE_KEY_TEMPOS_RESPOSTA}:{prioridade}"
        cache_key_resolucao = f"{SLAP90Incremental.CACHE_KEY_TEMPOS_RESOLUCAO}:{prioridade}"
        cache_key_ultimo_id = f"{SLAP90Incremental.CACHE_KEY_ULTIMO_ID}:{prioridade}"

        try:
            cache_resposta = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key_resposta
            ).first()

            cache_resolucao = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key_resolucao
            ).first()

            cache_ultimo_id = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key_ultimo_id
            ).first()

            tempos_resposta = []
            tempos_resolucao = []
            ultimo_id = 0

            if cache_resposta and cache_resposta.cache_value:
                try:
                    tempos_resposta = json.loads(cache_resposta.cache_value)
                except:
                    tempos_resposta = []

            if cache_resolucao and cache_resolucao.cache_value:
                try:
                    tempos_resolucao = json.loads(cache_resolucao.cache_value)
                except:
                    tempos_resolucao = []

            if cache_ultimo_id and cache_ultimo_id.cache_value:
                try:
                    ultimo_id = int(cache_ultimo_id.cache_value)
                except:
                    ultimo_id = 0

            return {
                "tempos_resposta": tempos_resposta,
                "tempos_resolucao": tempos_resolucao,
                "ultimo_id": ultimo_id,
                "total_anterior": len(tempos_resposta)
            }
        except Exception as e:
            print(f"[P90 INCREMENTAL] Erro ao carregar cache: {e}")
            return {
                "tempos_resposta": [],
                "tempos_resolucao": [],
                "ultimo_id": 0,
                "total_anterior": 0
            }

    @staticmethod
    def salvar_cache_prioridade(
        db: Session,
        prioridade: str,
        tempos_resposta: list[float],
        tempos_resolucao: list[float],
        ultimo_id: int
    ) -> bool:
        """Salva dados no cache para uma prioridade."""
        try:
            agora = now_brazil_naive()
            ttl_segundos = 30 * 24 * 60 * 60
            expira_em = agora + timedelta(seconds=ttl_segundos)

            cache_key_resposta = f"{SLAP90Incremental.CACHE_KEY_TEMPOS_RESPOSTA}:{prioridade}"
            cache_key_resolucao = f"{SLAP90Incremental.CACHE_KEY_TEMPOS_RESOLUCAO}:{prioridade}"
            cache_key_ultimo_id = f"{SLAP90Incremental.CACHE_KEY_ULTIMO_ID}:{prioridade}"

            # Resposta
            cache_resposta = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key_resposta
            ).first()

            if cache_resposta:
                cache_resposta.cache_value = json.dumps(tempos_resposta)
                cache_resposta.calculated_at = agora
                cache_resposta.expires_at = expira_em
            else:
                cache_resposta = MetricsCacheDB(
                    cache_key=cache_key_resposta,
                    cache_value=json.dumps(tempos_resposta),
                    calculated_at=agora,
                    expires_at=expira_em,
                )
            db.add(cache_resposta)

            # Resolução
            cache_resolucao = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key_resolucao
            ).first()

            if cache_resolucao:
                cache_resolucao.cache_value = json.dumps(tempos_resolucao)
                cache_resolucao.calculated_at = agora
                cache_resolucao.expires_at = expira_em
            else:
                cache_resolucao = MetricsCacheDB(
                    cache_key=cache_key_resolucao,
                    cache_value=json.dumps(tempos_resolucao),
                    calculated_at=agora,
                    expires_at=expira_em,
                )
            db.add(cache_resolucao)

            # Último ID
            cache_ultimo_id = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key_ultimo_id
            ).first()

            if cache_ultimo_id:
                cache_ultimo_id.cache_value = str(ultimo_id)
                cache_ultimo_id.calculated_at = agora
                cache_ultimo_id.expires_at = expira_em
            else:
                cache_ultimo_id = MetricsCacheDB(
                    cache_key=cache_key_ultimo_id,
                    cache_value=str(ultimo_id),
                    calculated_at=agora,
                    expires_at=expira_em,
                )
            db.add(cache_ultimo_id)

            db.commit()
            return True
        except Exception as e:
            print(f"[P90 INCREMENTAL] Erro ao salvar cache: {e}")
            db.rollback()
            return False

    @staticmethod
    def recalcular_incremental(db: Session) -> dict:
        """
        Recalcula SLA de forma INCREMENTAL.

        Busca apenas chamados posteriores ao último processado.
        Ignora chamados anteriores ao último reset (se houver).
        Combina com dados anteriores para calcular P90.
        """
        agora = now_brazil_naive()
        data_inicio = agora - timedelta(days=30)

        print(f"[P90 INCREMENTAL] Iniciando recálculo incremental")

        configs = db.query(SLAConfiguration).filter(
            SLAConfiguration.ativo == True
        ).all()

        resultado = {
            "sucesso": True,
            "data_atualizacao": agora.isoformat(),
            "periodo": f"{data_inicio.isoformat()} a {agora.isoformat()}",
            "prioridades": {}
        }

        for config in configs:
            prioridade = config.prioridade

            print(f"\n[P90 INCREMENTAL] Processando prioridade: {prioridade}")

            cache_anterior = SLAP90Incremental.carregar_cache_prioridade(db, prioridade)
            ultimo_id = cache_anterior["ultimo_id"]

            print(f"  - Total anterior em cache: {cache_anterior['total_anterior']}")
            print(f"  - Último ID processado: {ultimo_id}")

            if config.ultimo_reset_em:
                print(f"  - Último reset em: {config.ultimo_reset_em.isoformat()}")

            tempos_resposta = cache_anterior["tempos_resposta"].copy()
            tempos_resolucao = cache_anterior["tempos_resolucao"].copy()

            # Se houver reset, ignora dados anteriores e começa do zero
            if config.ultimo_reset_em:
                print(f"  - Sistema foi resetado! Iniciando cálculos do zero a partir de {config.ultimo_reset_em}")
                tempos_resposta = []
                tempos_resolucao = []
                ultimo_id = 0

            chamados_novos = db.query(Chamado).filter(
                and_(
                    Chamado.prioridade == prioridade,
                    Chamado.data_abertura >= data_inicio,
                    Chamado.data_abertura <= agora,
                    Chamado.deletado_em.is_(None),
                    Chamado.status.in_(["Concluído", "Cancelado"]),
                    Chamado.id > ultimo_id,
                    # Se houver reset, apenas chamados APÓS o reset
                    Chamado.data_abertura >= (config.ultimo_reset_em if config.ultimo_reset_em else data_inicio)
                )
            ).order_by(Chamado.id.asc()).all()

            print(f"  - Novos chamados encontrados: {len(chamados_novos)}")

            novo_maximo_id = ultimo_id
            chamados_processados = 0

            for chamado in chamados_novos:
                try:
                    tempo_resposta = SLAP90Incremental.obter_tempo_primeira_resposta(chamado, db)
                    tempo_resolucao = SLAP90Incremental.obter_tempo_resolucao(chamado, db)

                    if tempo_resposta > 0:
                        tempos_resposta.append(tempo_resposta)

                    if tempo_resolucao > 0:
                        tempos_resolucao.append(tempo_resolucao)

                    novo_maximo_id = max(novo_maximo_id, chamado.id)
                    chamados_processados += 1

                except Exception as e:
                    print(f"  ⚠️  Erro ao processar chamado {chamado.id}: {e}")

            print(f"  - Chamados processados com sucesso: {chamados_processados}")

            if len(tempos_resposta) > 0 and len(tempos_resolucao) > 0:
                p90_resposta = SLAP90Incremental.calcular_percentil_90(tempos_resposta)
                p90_resolucao = SLAP90Incremental.calcular_percentil_90(tempos_resolucao)

                margem_seguranca = 1.15
                tempo_resposta_final = p90_resposta * margem_seguranca
                tempo_resolucao_final = p90_resolucao * margem_seguranca

                tempo_resposta_horas = round(tempo_resposta_final)
                tempo_resolucao_horas = round(tempo_resolucao_final)

                config.tempo_resposta_horas = tempo_resposta_horas
                config.tempo_resolucao_horas = tempo_resolucao_horas
                config.atualizado_em = agora

                db.add(config)
                db.commit()

                SLAP90Incremental.salvar_cache_prioridade(
                    db,
                    prioridade,
                    tempos_resposta,
                    tempos_resolucao,
                    novo_maximo_id
                )

                print(f"  ✅ SLA Atualizado!")
                print(f"     - Total de tempos: {len(tempos_resposta)}")
                print(f"     - P90 Resposta: {p90_resposta:.2f}h → {tempo_resposta_horas}h")
                print(f"     - P90 Resolução: {p90_resolucao:.2f}h → {tempo_resolucao_horas}h")

                resultado["prioridades"][prioridade] = {
                    "sucesso": True,
                    "total_tempos_acumulados": len(tempos_resposta),
                    "novos_chamados": chamados_processados,
                    "p90_resposta_horas": round(p90_resposta, 2),
                    "p90_resolucao_horas": round(p90_resolucao, 2),
                    "tempo_resposta_novo": tempo_resposta_horas,
                    "tempo_resolucao_novo": tempo_resolucao_horas,
                    "margem_seguranca": margem_seguranca
                }
            else:
                print(f"  ⚠️  Sem dados suficientes para calcular P90")
                resultado["prioridades"][prioridade] = {
                    "sucesso": False,
                    "motivo": "Dados insuficientes para calcular P90",
                    "total_tempos": len(tempos_resposta)
                }

        SLACacheManager.invalidate_all_sla(db)

        print(f"\n[P90 INCREMENTAL] Recálculo concluído!")
        return resultado
