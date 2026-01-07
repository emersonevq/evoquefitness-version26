#!/usr/bin/env python3
"""
Script para recalcular SLA de TODOS os chamados do sistema de forma robusta.

Este script:
1. Recalcula o SLA para todos os chamados existentes
2. Atualiza a tabela de histórico de SLA
3. Computa estatísticas agregadas (tempo médio de resposta/resolução)
4. Pode ser executado periodicamente (recomendado: diariamente às 00:00)

Uso:
    python -m ti.scripts.recalculate_sla_complete
"""

import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

sys.path.insert(0, "/app/backend")

from core.db import SessionLocal, engine
from ti.models.chamado import Chamado
from ti.models.sla_config import HistoricoSLA, SLAConfiguration
from ti.models.historico_status import HistoricoStatus
from ti.services.sla import SLACalculator
from ti.services.sla_cache import SLACacheManager
from core.utils import now_brazil_naive


class SLARecalculator:
    """Recalcula SLA de forma robusta e eficiente"""

    def __init__(self, db: Session):
        self.db = db
        self.stats = {
            "total_chamados": 0,
            "recalculados": 0,
            "com_erro": 0,
            "tempo_medio_resposta_horas": 0.0,
            "tempo_medio_resolucao_horas": 0.0,
            "chamados_dentro_sla_resposta": 0,
            "chamados_dentro_sla_resolucao": 0,
            "detalhes": [],
        }

    def recalculate_all(self, verbose: bool = True) -> dict:
        """Recalcula SLA de todos os chamados"""
        if verbose:
            print("\n" + "=" * 80)
            print("RECALCULANDO SLA DE TODOS OS CHAMADOS")
            print("=" * 80 + "\n")

        try:
            # Carrega configurações de SLA uma vez (otimização)
            sla_configs = {
                config.prioridade: config
                for config in self.db.query(SLAConfiguration).filter(
                    SLAConfiguration.ativo == True
                ).all()
            }

            if not sla_configs:
                if verbose:
                    print("⚠️  AVISO: Nenhuma configuração de SLA encontrada!")
                return self.stats

            # Carrega todos os chamados
            chamados = self.db.query(Chamado).all()
            self.stats["total_chamados"] = len(chamados)

            if verbose:
                print(f"📊 Total de chamados para recalcular: {len(chamados)}")
                print(f"⚙️  Configurações de SLA encontradas: {len(sla_configs)}")
                print("-" * 80 + "\n")

            # Coleta tempos para calcular média
            tempos_resposta = []
            tempos_resolucao = []

            # Processa cada chamado
            for idx, chamado in enumerate(chamados, 1):
                try:
                    # Mostra progresso a cada 10 chamados
                    if verbose and idx % 10 == 0:
                        print(f"⏳ Processando: {idx}/{len(chamados)}...")

                    # Calcula SLA atual
                    sla_status = SLACalculator.get_sla_status(self.db, chamado)

                    if sla_status.get("status_geral") == "sem_sla":
                        continue

                    # Extrai métricas
                    resposta_metric = sla_status.get("resposta_metric", {})
                    resolucao_metric = sla_status.get("resolucao_metric", {})

                    tempo_resposta = resposta_metric.get("tempo_decorrido_horas", 0.0)
                    tempo_resolucao = resolucao_metric.get("tempo_decorrido_horas", 0.0)

                    # Coleta para média (apenas fechados para tempo de resposta/resolução definitivos)
                    if chamado.status in ["Concluido", "Concluído", "Cancelado"]:
                        if tempo_resposta > 0:
                            tempos_resposta.append(tempo_resposta)
                        if tempo_resolucao > 0:
                            tempos_resolucao.append(tempo_resolucao)

                    # Verifica se estão dentro do SLA
                    sla_config = sla_configs.get(chamado.prioridade)
                    if sla_config:
                        if tempo_resposta <= sla_config.tempo_resposta_horas:
                            self.stats["chamados_dentro_sla_resposta"] += 1
                        if tempo_resolucao <= sla_config.tempo_resolucao_horas:
                            self.stats["chamados_dentro_sla_resolucao"] += 1

                    # Atualiza ou cria histórico de SLA
                    self._update_sla_history(chamado, sla_status, sla_configs)

                    self.stats["recalculados"] += 1

                except Exception as e:
                    self.stats["com_erro"] += 1
                    self.stats["detalhes"].append({
                        "chamado_id": chamado.id,
                        "codigo": getattr(chamado, "codigo", "?"),
                        "erro": str(e),
                    })

            # Calcula médias
            if tempos_resposta:
                self.stats["tempo_medio_resposta_horas"] = sum(tempos_resposta) / len(tempos_resposta)
            if tempos_resolucao:
                self.stats["tempo_medio_resolucao_horas"] = sum(tempos_resolucao) / len(tempos_resolucao)

            # Invalida cache de métricas
            SLACacheManager.invalidate_all_sla(self.db)

            if verbose:
                self._print_stats()

            return self.stats

        except Exception as e:
            print(f"❌ Erro crítico durante recalculação: {e}")
            import traceback
            traceback.print_exc()
            return self.stats

    def _update_sla_history(self, chamado: Chamado, sla_status: dict, sla_configs: dict):
        """Atualiza ou cria registro de histórico de SLA"""
        try:
            # Busca histórico existente
            existing = self.db.query(HistoricoSLA).filter(
                HistoricoSLA.chamado_id == chamado.id
            ).order_by(HistoricoSLA.criado_em.desc()).first()

            resposta_metric = sla_status.get("resposta_metric", {})
            resolucao_metric = sla_status.get("resolucao_metric", {})

            tempo_resposta = resposta_metric.get("tempo_decorrido_horas", 0.0)
            tempo_resolucao = resolucao_metric.get("tempo_decorrido_horas", 0.0)

            if existing:
                # Atualiza registro existente
                existing.tempo_resposta_horas = tempo_resposta
                existing.tempo_resolucao_horas = tempo_resolucao
                existing.status_novo = chamado.status
                existing.status_sla = sla_status.get("status_geral")
                existing.atualizado_em = now_brazil_naive()
                self.db.add(existing)
            else:
                # Cria novo registro
                historico = HistoricoSLA(
                    chamado_id=chamado.id,
                    usuario_id=None,
                    acao="recalculo_automatico",
                    status_novo=chamado.status,
                    tempo_resposta_horas=tempo_resposta,
                    tempo_resolucao_horas=tempo_resolucao,
                    status_sla=sla_status.get("status_geral"),
                    criado_em=chamado.data_abertura or now_brazil_naive(),
                )
                self.db.add(historico)

            self.db.flush()

        except Exception as e:
            print(f"⚠️  Erro ao atualizar histórico do chamado {chamado.id}: {e}")
            raise

    def _print_stats(self):
        """Imprime estatísticas da recalculação"""
        print("\n" + "=" * 80)
        print("📈 ESTATÍSTICAS DE RECALCULAÇÃO")
        print("=" * 80)
        print(f"✅ Total de chamados: {self.stats['total_chamados']}")
        print(f"✅ Recalculados: {self.stats['recalculados']}")
        print(f"❌ Com erro: {self.stats['com_erro']}")
        print()
        print(f"⏱️  Tempo médio de resposta: {self.stats['tempo_medio_resposta_horas']:.2f}h")
        print(f"⏱️  Tempo médio de resolução: {self.stats['tempo_medio_resolucao_horas']:.2f}h")
        print()
        print(f"📊 Chamados dentro do SLA (resposta): {self.stats['chamados_dentro_sla_resposta']}")
        print(f"📊 Chamados dentro do SLA (resolução): {self.stats['chamados_dentro_sla_resolucao']}")
        print("=" * 80 + "\n")


def main():
    """Executa a recalculação"""
    db = SessionLocal()
    try:
        recalculator = SLARecalculator(db)
        stats = recalculator.recalculate_all(verbose=True)
        db.commit()
        return 0
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
