"""
Gerenciador de Cache Incremental

Estratégia:
1. Cache de mês inteiro que persiste até final do mês
2. Counter separado para "chamados hoje" com reset à meia-noite
3. Cálculos incrementais quando chamado é alterado
4. Atualização via WebSocket para frontend em tempo real

Garantias:
- Cache mensal persiste até dia 1 do próximo mês
- "Chamados hoje" reseta automaticamente à 00:00
- Alterações em chamados recalculam incrementalmente
- Frontend recebe updates em tempo real via WebSocket
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ti.models.chamado import Chamado
from ti.models.metrics_cache import MetricsCacheDB
from ti.models.sla_config import SLAConfiguration
from ti.models.historico_status import HistoricoStatus
from core.utils import now_brazil_naive
import json
from typing import Optional, Dict, Any


class ChamadosTodayCounter:
    """
    Counter para "chamados hoje" com reset automático à meia-noite.
    
    Armazenado no banco como cache com chave especial "chamados_hoje_{data}"
    Permite recuperar valor mesmo após reinicialização do servidor.
    """
    
    @staticmethod
    def get_cache_key_today() -> str:
        """Gera chave de cache baseada na data de hoje"""
        hoje = now_brazil_naive().date().isoformat()
        return f"chamados_hoje:{hoje}"
    
    @staticmethod
    def get_cache_key_for_date(date: datetime) -> str:
        """Gera chave de cache para uma data específica"""
        return f"chamados_hoje:{date.date().isoformat()}"
    
    @staticmethod
    def get_count(db: Session) -> int:
        """Obtém contador de chamados de hoje"""
        try:
            cache_key = ChamadosTodayCounter.get_cache_key_today()
            
            cached = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key
            ).first()
            
            if cached and cached.expires_at and cached.expires_at > now_brazil_naive():
                try:
                    return int(json.loads(cached.cache_value))
                except:
                    return 0
            
            # Se expirou, recalcula (isso só deve acontecer após meia-noite)
            return ChamadosTodayCounter._recalculate(db)
        
        except Exception as e:
            print(f"[CACHE] Erro ao obter contador de hoje: {e}")
            return 0
    
    @staticmethod
    def increment(db: Session, count: int = 1) -> int:
        """Incrementa contador de chamados de hoje"""
        try:
            cache_key = ChamadosTodayCounter.get_cache_key_today()

            # Obtém valor atual
            cached = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key
            ).first()

            # Se expirou (passou meia-noite), recalcula
            if not cached or (cached.expires_at and cached.expires_at <= now_brazil_naive()):
                new_value = ChamadosTodayCounter._recalculate(db)
                return new_value + count

            # Incrementa o valor existente
            try:
                current_value = int(json.loads(cached.cache_value))
            except:
                current_value = 0

            new_value = current_value + count

            # Atualiza cache com expire à meia-noite
            agora = now_brazil_naive()
            proximo_dia = (agora + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            cached.cache_value = json.dumps(new_value)
            cached.calculated_at = agora
            cached.expires_at = proximo_dia
            db.add(cached)
            db.commit()

            return new_value

        except Exception as e:
            print(f"[CACHE] Erro ao incrementar contador: {e}")
            try:
                db.rollback()
            except:
                pass
            return ChamadosTodayCounter._recalculate(db)
    
    @staticmethod
    def decrement(db: Session, count: int = 1) -> int:
        """Decrementa contador de chamados de hoje (para cancelamentos)"""
        try:
            cache_key = ChamadosTodayCounter.get_cache_key_today()
            
            cached = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == cache_key
            ).first()
            
            if not cached or (cached.expires_at and cached.expires_at <= now_brazil_naive()):
                return ChamadosTodayCounter._recalculate(db)
            
            try:
                current_value = int(json.loads(cached.cache_value))
            except:
                current_value = 0
            
            new_value = max(0, current_value - count)

            agora = now_brazil_naive()
            proximo_dia = (agora + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            try:
                cached.cache_value = json.dumps(new_value)
                cached.calculated_at = agora
                cached.expires_at = proximo_dia
                db.add(cached)
                db.commit()
            except Exception as commit_error:
                db.rollback()
                print(f"[CACHE] Erro ao commit decrement: {commit_error}")
                raise

            return new_value

        except Exception as e:
            print(f"[CACHE] Erro ao decrementar contador: {e}")
            try:
                db.rollback()
            except:
                pass
            return ChamadosTodayCounter._recalculate(db)
    
    @staticmethod
    def _recalculate(db: Session) -> int:
        """Recalcula contador de hoje a partir do banco de dados"""
        try:
            hoje = now_brazil_naive().replace(hour=0, minute=0, second=0, microsecond=0)

            count = db.query(Chamado).filter(
                and_(
                    Chamado.data_abertura >= hoje,
                    Chamado.status != "Cancelado"
                )
            ).count()

            # Salva no cache com expire à meia-noite
            cache_key = ChamadosTodayCounter.get_cache_key_today()
            agora = now_brazil_naive()
            proximo_dia = (agora + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            try:
                existing = db.query(MetricsCacheDB).filter(
                    MetricsCacheDB.cache_key == cache_key
                ).first()

                if existing:
                    existing.cache_value = json.dumps(count)
                    existing.calculated_at = agora
                    existing.expires_at = proximo_dia
                    db.add(existing)
                else:
                    new_cache = MetricsCacheDB(
                        cache_key=cache_key,
                        cache_value=json.dumps(count),
                        calculated_at=agora,
                        expires_at=proximo_dia,
                    )
                    db.add(new_cache)

                db.commit()
            except Exception as commit_error:
                db.rollback()
                print(f"[CACHE] Erro ao commit recalculate: {commit_error}")

            return count

        except Exception as e:
            print(f"[CACHE] Erro ao recalcular contador: {e}")
            try:
                db.rollback()
            except:
                pass
            return 0


class IncrementalMetricsCache:
    """
    Cache de métricas mensais com cálculos incrementais.
    
    Estratégia:
    - Cache persiste até final do mês (dia 28/29/30/31 às 23:59:59)
    - Quando um chamado é alterado, recalcula apenas aquele chamado
    - Soma resultado com cache base para obter novas métricas
    - Reset automático no dia 1º do próximo mês às 00:00
    """
    
    @staticmethod
    def get_cache_key_month() -> str:
        """Gera chave de cache para o mês atual"""
        agora = now_brazil_naive()
        ano_mes = agora.strftime("%Y-%m")
        return f"sla_metrics_mes:{ano_mes}"
    
    @staticmethod
    def get_expire_time_for_month() -> datetime:
        """Retorna data/hora do último segundo do mês"""
        agora = now_brazil_naive()
        
        # Calcula último dia do mês
        if agora.month == 12:
            proximo_mes = agora.replace(year=agora.year + 1, month=1, day=1)
        else:
            proximo_mes = agora.replace(month=agora.month + 1, day=1)
        
        # Último segundo do mês = um segundo antes de virar para o próximo mês
        ultimo_segundo = proximo_mes - timedelta(seconds=1)
        return ultimo_segundo
    
    @staticmethod
    def get_metrics(db: Session) -> Dict[str, Any]:
        """Obtém métricas mensais do cache com fallback robusto"""
        try:
            cache_key = IncrementalMetricsCache.get_cache_key_month()

            # Tenta obter do cache
            try:
                cached = db.query(MetricsCacheDB).filter(
                    MetricsCacheDB.cache_key == cache_key
                ).first()

                if cached and cached.expires_at and cached.expires_at > now_brazil_naive():
                    try:
                        metrics = json.loads(cached.cache_value)
                        # Validação básica
                        if all(k in metrics for k in ["total", "dentro_sla", "fora_sla"]):
                            return metrics
                    except (json.JSONDecodeError, ValueError):
                        print(f"[CACHE] Cache corrompido para {cache_key}, recalculando...")
                        pass
            except Exception as cache_error:
                print(f"[CACHE] Erro ao buscar cache do banco: {cache_error}")
                pass

            # Cache não existe ou expirou, recalcula (de forma otimizada)
            return IncrementalMetricsCache._calculate_month(db)

        except Exception as e:
            print(f"[CACHE] Erro ao obter métricas mensais: {e}")
            # Retorna valores seguros
            return {
                "total": 0,
                "dentro_sla": 0,
                "fora_sla": 0,
                "percentual_dentro": 0,
                "percentual_fora": 0,
            }
    
    @staticmethod
    def update_for_chamado(db: Session, chamado_id: int) -> None:
        """
        Atualiza métricas incrementalmente quando um chamado é alterado.
        
        Em vez de recalcular TUDO, calcula apenas aquele chamado
        e soma com as métricas em cache.
        """
        try:
            chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
            if not chamado:
                return
            
            # Obtém métricas atuais do cache
            metricas_atuais = IncrementalMetricsCache.get_metrics(db)
            
            # Calcula o status SLA deste chamado
            from ti.services.sla import SLACalculator
            sla_config = SLACalculator.get_sla_config_by_priority(db, chamado.prioridade)
            
            if not sla_config:
                return
            
            # Determina se está dentro/fora SLA
            agora = now_brazil_naive()
            data_abertura = chamado.data_abertura or agora
            data_final = chamado.data_conclusao if chamado.data_conclusao else agora

            tempo_resolucao = SLACalculator.calculate_business_hours_excluding_paused(
                chamado.id,
                data_abertura,
                data_final,
                db
            )
            
            esta_dentro_sla = tempo_resolucao <= sla_config.tempo_resolucao_horas
            
            # Atualiza métricas (incremental)
            novo_dentro = metricas_atuais["dentro_sla"]
            novo_fora = metricas_atuais["fora_sla"]
            
            # Remove contagem anterior do chamado (se existe)
            historico_anterior = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == f"chamado_sla_status:{chamado_id}"
            ).first()
            
            estava_dentro = True
            if historico_anterior:
                try:
                    data_anterior = json.loads(historico_anterior.cache_value)
                    estava_dentro = data_anterior.get("dentro_sla", True)
                    
                    # Remove contagem anterior
                    if estava_dentro:
                        novo_dentro -= 1
                    else:
                        novo_fora -= 1
                except:
                    pass
            
            # Adiciona nova contagem
            if esta_dentro_sla:
                novo_dentro += 1
            else:
                novo_fora += 1
            
            # Calcula novo percentual
            total = novo_dentro + novo_fora
            novo_percentual_dentro = int((novo_dentro / total) * 100) if total > 0 else 0
            novo_percentual_fora = 100 - novo_percentual_dentro
            
            # Atualiza cache mensal
            metricas_atuais["dentro_sla"] = novo_dentro
            metricas_atuais["fora_sla"] = novo_fora
            metricas_atuais["percentual_dentro"] = novo_percentual_dentro
            metricas_atuais["percentual_fora"] = novo_percentual_fora
            metricas_atuais["total"] = total
            
            IncrementalMetricsCache._save_metrics(db, metricas_atuais)
            
            # Armazena status do chamado para próximas atualizações
            IncrementalMetricsCache._save_chamado_status(
                db, chamado_id, dentro_sla=esta_dentro_sla
            )
        
        except Exception as e:
            print(f"[CACHE] Erro ao atualizar métricas para chamado {chamado_id}: {e}")
    
    @staticmethod
    def _calculate_month(db: Session) -> Dict[str, Any]:
        """Calcula métricas mensais do zero com debouncing"""
        try:
            from ti.services.sla_metrics_unified import UnifiedSLAMetricsCalculator
            from ti.services.cache_debouncer import get_debouncer

            debouncer = get_debouncer()
            cache_key = IncrementalMetricsCache.get_cache_key_month()

            # Usa debouncer para evitar múltiplos recálculos simultâneos
            def calculate_metrics():
                agora = now_brazil_naive()
                mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                # Usa calculador unificado para mês
                dist = UnifiedSLAMetricsCalculator.calculate_sla_distribution_period(
                    db, mes_inicio, agora
                )

                metricas = {
                    "total": dist["total"],
                    "dentro_sla": dist["dentro_sla"],
                    "fora_sla": dist["fora_sla"],
                    "percentual_dentro": dist["percentual_dentro"],
                    "percentual_fora": dist["percentual_fora"],
                    "updated_at": agora.isoformat(),
                }

                # Salva no cache
                IncrementalMetricsCache._save_metrics(db, metricas)

                return metricas

            # Debounce o cálculo por 300 segundos (5 minutos)
            result = debouncer.debounce(
                key=cache_key,
                func=calculate_metrics,
                ttl=300,  # Cache resultado por 5 minutos
                timeout=120  # Espera até 2 minutos por cálculo anterior
            )

            if result is None:
                # Fallback se debounce falhar
                return {
                    "total": 0,
                    "dentro_sla": 0,
                    "fora_sla": 0,
                    "percentual_dentro": 0,
                    "percentual_fora": 0,
                }

            return result

        except Exception as e:
            print(f"[CACHE] Erro ao calcular métricas mensais: {e}")
            return {
                "total": 0,
                "dentro_sla": 0,
                "fora_sla": 0,
                "percentual_dentro": 0,
                "percentual_fora": 0,
            }
    
    @staticmethod
    def _save_metrics(db: Session, metricas: Dict[str, Any]) -> None:
        """Salva métricas no cache com expiração até fim do mês"""
        try:
            from sqlalchemy import insert
            cache_key = IncrementalMetricsCache.get_cache_key_month()
            expire_time = IncrementalMetricsCache.get_expire_time_for_month()

            agora = now_brazil_naive()
            cache_value = json.dumps(metricas)

            try:
                existing = db.query(MetricsCacheDB).filter(
                    MetricsCacheDB.cache_key == cache_key
                ).first()

                if existing:
                    existing.cache_value = cache_value
                    existing.calculated_at = agora
                    existing.expires_at = expire_time
                    db.add(existing)
                else:
                    new_cache = MetricsCacheDB(
                        cache_key=cache_key,
                        cache_value=cache_value,
                        calculated_at=agora,
                        expires_at=expire_time,
                    )
                    db.add(new_cache)

                db.commit()
            except Exception as commit_error:
                db.rollback()
                print(f"[CACHE] Erro ao commit métricas: {commit_error}")
        
        except Exception as e:
            print(f"[CACHE] Erro ao salvar métricas: {e}")
            try:
                db.rollback()
            except:
                pass
    
    @staticmethod
    def _save_chamado_status(
        db: Session,
        chamado_id: int,
        dentro_sla: bool
    ) -> None:
        """Salva status de SLA do chamado para referência incremental"""
        try:
            from sqlalchemy import insert
            cache_key = f"chamado_sla_status:{chamado_id}"

            expire_time = IncrementalMetricsCache.get_expire_time_for_month()
            agora = now_brazil_naive()

            cache_value = json.dumps({"dentro_sla": dentro_sla})

            try:
                existing = db.query(MetricsCacheDB).filter(
                    MetricsCacheDB.cache_key == cache_key
                ).first()

                if existing:
                    existing.cache_value = cache_value
                    existing.calculated_at = agora
                    existing.expires_at = expire_time
                    db.add(existing)
                else:
                    new_cache = MetricsCacheDB(
                        cache_key=cache_key,
                        cache_value=cache_value,
                        calculated_at=agora,
                        expires_at=expire_time,
                    )
                    db.add(new_cache)

                db.commit()
            except Exception as commit_error:
                db.rollback()
                print(f"[CACHE] Erro ao commit status do chamado: {commit_error}")

        except Exception as e:
            print(f"[CACHE] Erro ao salvar status do chamado: {e}")
            try:
                db.rollback()
            except:
                pass
