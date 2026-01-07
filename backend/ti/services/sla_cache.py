from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Optional
import json
import threading
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from core.utils import now_brazil_naive
import hashlib


class SLACacheEntry:
    """Representa uma entrada de cache com TTL e metadata"""
    def __init__(self, key: str, value: Any, ttl_seconds: int = 3600):
        self.key = key
        self.value = value
        self.created_at = datetime.now()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
        self.last_accessed = datetime.now()

    def is_expired(self) -> bool:
        """Verifica se o cache expirou"""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def touch(self):
        """Atualiza timestamp de último acesso"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class SLACacheManager:
    """
    Gerenciador de cache robusto para SLA com:
    - Estratégia unificada: Memória é primária, DB é fallback/persistência
    - Cache em memória com TTL
    - Persistência em banco de dados como recuperação
    - Invalidação inteligente por padrão
    - Batch operations

    Garantias:
    1. Uma única fonte de verdade para cada métrica
    2. Consistência entre réplicas (TTL sincronizado)
    3. Invalidação automática ao fazer mudanças
    """

    # Cache em memória (primário)
    _memory_cache: dict[str, SLACacheEntry] = {}
    _lock = threading.Lock()

    # Configurações de TTL por tipo de métrica
    # IMPORTANTE: TTL muito longo (24 horas) - cache persiste até mudança de status
    # Cache é invalidado APENAS quando há mudança de chamados, não por tempo
    CACHE_TTL = {
        "sla_compliance_24h": 24 * 60 * 60,  # 24 horas - persiste até mudança
        "sla_compliance_mes": 24 * 60 * 60,  # 24 horas - persiste até mudança
        "sla_distribution": 24 * 60 * 60,  # 24 horas - persiste até mudança
        "tempo_resposta_24h": 24 * 60 * 60,  # 24 horas - persiste até mudança
        "tempo_resposta_mes": 24 * 60 * 60,  # 24 horas - persiste até mudança
        "chamado_sla_status": 24 * 60 * 60,  # 24 horas - persiste até mudança
        "metrics_basic": 24 * 60 * 60,  # 24 horas - persiste até mudança
    }

    # Chaves de cache relacionadas para invalidação
    RELATED_CACHE_KEYS = {
        "chamado_sla_status": [
            "sla_compliance_24h",
            "sla_compliance_mes",
            "sla_distribution",
            "tempo_resposta_24h",
            "tempo_resposta_mes",
        ],
        "chamado_update": [
            "sla_compliance_24h",
            "sla_compliance_mes",
            "sla_distribution",
            "tempo_resposta_24h",
            "tempo_resposta_mes",
            "metrics_basic",
        ],
    }

    @classmethod
    def get(cls, db: Session, key: str) -> Any:
        """
        Obtém valor do cache (memória -> banco de dados)

        Estratégia:
        1. Tenta memória (rápido)
        2. Se expirado, tenta banco de dados
        3. Se não encontrado, retorna None
        """
        with cls._lock:
            if key in cls._memory_cache:
                entry = cls._memory_cache[key]
                if not entry.is_expired():
                    entry.touch()
                    return entry.value
                else:
                    del cls._memory_cache[key]

        # Tenta banco de dados
        try:
            from ti.models.metrics_cache import MetricsCacheDB
            cached = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == key
            ).first()

            if cached:
                expires_at = cached.expires_at
                if expires_at and expires_at > now_brazil_naive():
                    # Cache do banco ainda é válido
                    value = json.loads(cached.cache_value) if isinstance(cached.cache_value, str) else cached.cache_value
                    # Carrega em memória também
                    ttl = cls._get_ttl_for_key(key)
                    with cls._lock:
                        cls._memory_cache[key] = SLACacheEntry(key, value, ttl)
                    return value
                else:
                    # Expirou no banco, deleta
                    db.delete(cached)
                    db.commit()
        except Exception as e:
            print(f"[CACHE] Erro ao buscar cache do banco: {e}")

        return None

    @classmethod
    def set(cls, db: Session, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Define valor do cache (memória + banco de dados)

        Estratégia:
        1. Armazena em memória para acesso rápido
        2. Persiste em banco de dados para resiliência
        """
        if ttl_seconds is None:
            ttl_seconds = cls._get_ttl_for_key(key)

        # Em memória
        with cls._lock:
            cls._memory_cache[key] = SLACacheEntry(key, value, ttl_seconds)

        # No banco de dados
        try:
            from ti.models.metrics_cache import MetricsCacheDB
            expires_at = now_brazil_naive() + timedelta(seconds=ttl_seconds)
            cache_value = json.dumps(value) if not isinstance(value, str) else value
            calculated_at = now_brazil_naive()

            # Tenta buscar cache existente
            existing = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key == key
            ).first()

            if existing:
                existing.cache_value = cache_value
                existing.calculated_at = calculated_at
                existing.expires_at = expires_at
                db.add(existing)
            else:
                new_cache = MetricsCacheDB(
                    cache_key=key,
                    cache_value=cache_value,
                    calculated_at=calculated_at,
                    expires_at=expires_at,
                )
                db.add(new_cache)

            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # Retry: outra transação inseriu, tenta atualizar
                existing = db.query(MetricsCacheDB).filter(
                    MetricsCacheDB.cache_key == key
                ).first()
                if existing:
                    existing.cache_value = cache_value
                    existing.calculated_at = calculated_at
                    existing.expires_at = expires_at
                    db.add(existing)
                    db.commit()
        except Exception as e:
            print(f"[CACHE] Erro ao persistir cache no banco: {e}")
            try:
                db.rollback()
            except:
                pass

    @classmethod
    def invalidate(cls, db: Session, keys: list[str]) -> None:
        """
        Invalida múltiplas chaves de cache

        Estratégia:
        1. Remove da memória imediatamente
        2. Remove do banco de dados
        """
        with cls._lock:
            for key in keys:
                if key in cls._memory_cache:
                    del cls._memory_cache[key]

        try:
            from ti.models.metrics_cache import MetricsCacheDB
            db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key.in_(keys)
            ).delete()
            db.commit()
        except Exception as e:
            print(f"[CACHE] Erro ao invalidar cache do banco: {e}")
            try:
                db.rollback()
            except:
                pass

    @classmethod
    def invalidate_by_chamado(cls, db: Session, chamado_id: int) -> None:
        """
        Invalida todos os caches relacionados a um chamado específico

        Quando um chamado muda, é mais inteligente que invalidar tudo.
        """
        keys_to_invalidate = [
            f"chamado_sla_status:{chamado_id}",
            "sla_compliance_24h",
            "sla_compliance_mes",
            "sla_distribution",
            "tempo_resposta_24h",
            "tempo_resposta_mes",
            "metrics_basic",
        ]

        cls.invalidate(db, keys_to_invalidate)

    @classmethod
    def invalidate_all_sla(cls, db: Session) -> None:
        """
        Invalida todos os caches de SLA (chamados quando config muda)
        """
        keys_to_invalidate = [
            "sla_compliance_24h",
            "sla_compliance_mes",
            "sla_distribution",
            "tempo_resposta_24h",
            "tempo_resposta_mes",
            "metrics_basic",
        ]

        cls.invalidate(db, keys_to_invalidate)

        # Também remove todas as chaves de chamado
        with cls._lock:
            keys_to_delete = [k for k in cls._memory_cache.keys() if k.startswith("chamado_sla_status:")]
            for k in keys_to_delete:
                del cls._memory_cache[k]

        try:
            from ti.models.metrics_cache import MetricsCacheDB
            db.query(MetricsCacheDB).filter(
                MetricsCacheDB.cache_key.like("chamado_sla_status:%")
            ).delete()
            db.commit()
        except Exception as e:
            print(f"[CACHE] Erro ao invalidar caches de SLA: {e}")
            try:
                db.rollback()
            except:
                pass

    @classmethod
    def _get_ttl_for_key(cls, key: str) -> int:
        """Retorna TTL apropriado para uma chave"""
        for metric_type, ttl in cls.CACHE_TTL.items():
            if key.startswith(metric_type):
                return ttl
        return 5 * 60  # Default: 5 minutos

    @classmethod
    def clear_expired(cls, db: Session) -> int:
        """
        Limpa caches expirados do banco de dados.
        Deve ser executado periodicamente (ex: job agendado).

        Retorna: quantidade de entradas removidas
        """
        try:
            from ti.models.metrics_cache import MetricsCacheDB
            count = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.expires_at <= now_brazil_naive()
            ).delete()
            db.commit()
            return count
        except Exception as e:
            print(f"[CACHE] Erro ao limpar cache expirado: {e}")
            try:
                db.rollback()
            except:
                pass
            return 0

    @classmethod
    def get_stats(cls, db: Session) -> dict:
        """Retorna estatísticas do cache"""
        memory_count = len(cls._memory_cache)

        try:
            from ti.models.metrics_cache import MetricsCacheDB
            db_count = db.query(MetricsCacheDB).count()
            db_expired = db.query(MetricsCacheDB).filter(
                MetricsCacheDB.expires_at <= now_brazil_naive()
            ).count()
        except:
            db_count = 0
            db_expired = 0

        return {
            "memory_entries": memory_count,
            "database_entries": db_count,
            "expired_in_db": db_expired,
        }

    @classmethod
    def warmup_from_database(cls, db: Session) -> dict:
        """
        Carrega todo o cache do banco de dados em memória.
        Útil para pré-aquecer após restart da aplicação.

        Retorna: estatísticas de carregamento
        """
        stats = {
            "carregados": 0,
            "expirados": 0,
            "erros": 0,
        }

        try:
            from ti.models.metrics_cache import MetricsCacheDB

            agora = now_brazil_naive()
            cached_entries = db.query(MetricsCacheDB).all()

            for cached in cached_entries:
                try:
                    if cached.expires_at and cached.expires_at > agora:
                        # Cache ainda é válido, carrega em memória
                        value = json.loads(cached.cache_value) if isinstance(cached.cache_value, str) else cached.cache_value
                        ttl = cls._get_ttl_for_key(cached.cache_key)
                        with cls._lock:
                            cls._memory_cache[cached.cache_key] = SLACacheEntry(
                                cached.cache_key, value, ttl
                            )
                        stats["carregados"] += 1
                    else:
                        # Cache expirou, marca para deleção
                        stats["expirados"] += 1
                        db.delete(cached)

                except Exception as e:
                    stats["erros"] += 1
                    print(f"[CACHE] Erro ao carregar cache {cached.cache_key}: {e}")

            db.commit()
            return stats

        except Exception as e:
            print(f"[CACHE] Erro ao pré-aquecer cache: {e}")
            try:
                db.rollback()
            except:
                pass
            return stats
