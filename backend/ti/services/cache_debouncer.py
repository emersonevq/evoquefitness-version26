"""
Cache Debouncer - Evita múltiplos recálculos simultâneos

Quando múltiplas requisições tentam recalcular métricas ao mesmo tempo,
este sistema garante que apenas um recálculo acontece, e os outros esperam.

Isso reduz carga no banco de dados durante picos de tráfego.
"""

import threading
import time
from typing import Optional, Callable, Any
from datetime import datetime, timedelta


class CacheDebouncer:
    """
    Gerenciador de debouncing para operações caras.
    
    Uso:
        debouncer = CacheDebouncer()
        result = debouncer.debounce(
            key="metrics_month",
            func=lambda: expensive_calculation(),
            ttl=300  # 5 minutos
        )
    """
    
    def __init__(self):
        self._locks: dict[str, threading.RLock] = {}
        self._in_progress: dict[str, bool] = {}
        self._last_result: dict[str, tuple[Any, datetime]] = {}
        self._lock = threading.RLock()
    
    def _get_lock(self, key: str) -> threading.RLock:
        """Obtém ou cria lock para a chave"""
        with self._lock:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            return self._locks[key]
    
    def debounce(
        self,
        key: str,
        func: Callable[[], Any],
        ttl: int = 300,
        timeout: int = 60
    ) -> Optional[Any]:
        """
        Executa função uma vez, mesmo com múltiplas chamadas simultâneas.
        
        Args:
            key: Identificador único da operação
            func: Função a executar
            ttl: Tempo em segundos para cache de resultado
            timeout: Tempo em segundos para esperar por resultado
            
        Returns:
            Resultado da função ou None se timeout
        """
        lock = self._get_lock(key)
        
        # Se já tem resultado em cache e ainda é válido, retorna
        with self._lock:
            if key in self._last_result:
                result, timestamp = self._last_result[key]
                age = (datetime.now() - timestamp).total_seconds()
                if age < ttl:
                    return result
        
        # Tenta adquirir lock (wait para evitar n operações simultâneas)
        acquired = lock.acquire(timeout=timeout)
        
        if not acquired:
            # Timeout ao esperar lock, mas retorna cache antigo se existir
            with self._lock:
                if key in self._last_result:
                    result, _ = self._last_result[key]
                    return result
            return None
        
        try:
            # Verifica novamente se resultado foi calculado enquanto aguardava lock
            with self._lock:
                if key in self._last_result:
                    result, timestamp = self._last_result[key]
                    age = (datetime.now() - timestamp).total_seconds()
                    if age < ttl:
                        return result
            
            # Marca como em progresso
            with self._lock:
                self._in_progress[key] = True
            
            try:
                # Executa função (pode demorar)
                result = func()
                
                # Salva resultado
                with self._lock:
                    self._last_result[key] = (result, datetime.now())
                    self._in_progress[key] = False
                
                return result
            
            except Exception as e:
                print(f"[DEBOUNCER] Erro ao executar {key}: {e}")
                
                # Retorna último resultado mesmo se houve erro
                with self._lock:
                    self._in_progress[key] = False
                    if key in self._last_result:
                        result, _ = self._last_result[key]
                        return result
                
                raise
        
        finally:
            lock.release()
    
    def invalidate(self, key: str) -> None:
        """Invalida cache para uma chave"""
        with self._lock:
            if key in self._last_result:
                del self._last_result[key]
    
    def is_in_progress(self, key: str) -> bool:
        """Verifica se cálculo está em progresso"""
        with self._lock:
            return self._in_progress.get(key, False)
    
    def get_stats(self) -> dict:
        """Retorna estatísticas"""
        with self._lock:
            return {
                "cached_keys": len(self._last_result),
                "in_progress": len([k for k, v in self._in_progress.items() if v]),
            }


# Instância global
_debouncer = CacheDebouncer()


def get_debouncer() -> CacheDebouncer:
    """Obtém instância global do debouncer"""
    return _debouncer
