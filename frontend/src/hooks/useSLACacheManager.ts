import { useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface CacheWarmupStats {
  total_calculados: number;
  tempo_ms: number;
  erro: null | string;
}

interface CacheStats {
  memory_entries: number;
  database_entries: number;
  expired_in_db: number;
}

/**
 * Hook para gerenciar cache de SLA de forma inteligente
 *
 * Features:
 * - Pré-aquecimento de cache ao abrir painel
 * - Invalidação automática quando chamados mudam
 * - Limpeza de cache expirado
 * - Estatísticas de cache
 */
export function useSLACacheManager() {
  const queryClient = useQueryClient();

  // Pré-aquece cache quando painel é aberto
  const warmupCache = useCallback(async () => {
    try {
      const response = await api.post("/sla/cache/warmup");
      const stats = response.data as CacheWarmupStats;

      console.log(
        `[CACHE] Warmup concluído: ${stats.total_calculados} métricas em ${stats.tempo_ms}ms`,
      );

      return stats;
    } catch (error) {
      console.error("[CACHE] Erro ao aquecimento de cache:", error);
      throw error;
    }
  }, []);

  // Invalida cache de um chamado específico
  const invalidateChamado = useCallback(
    async (chamadoId: number) => {
      try {
        await api.post(`/sla/cache/invalidate-chamado/${chamadoId}`);

        // Invalida queries do React Query relacionadas
        queryClient.invalidateQueries({ queryKey: ["sla-status-realtime"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-dashboard"] });

        console.log(`[CACHE] Cache do chamado #${chamadoId} invalidado`);
      } catch (error) {
        console.error(`[CACHE] Erro ao invalidar cache do chamado: ${error}`);
      }
    },
    [queryClient],
  );

  // Invalida TODOS os caches (quando config de SLA muda)
  const invalidateAll = useCallback(async () => {
    try {
      await api.post("/sla/cache/invalidate-all");

      // Invalida todas as queries de SLA e métricas
      queryClient.invalidateQueries({ queryKey: ["sla-"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-"] });
      queryClient.invalidateQueries({ queryKey: ["sla-config"] });

      console.log("[CACHE] Todos os caches de SLA invalidados");
    } catch (error) {
      console.error("[CACHE] Erro ao invalidar todos os caches:", error);
    }
  }, [queryClient]);

  // Obtém estatísticas do cache
  const getStats = useCallback(async () => {
    try {
      const response = await api.get("/sla/cache/stats");
      return response.data as CacheStats;
    } catch (error) {
      console.error("[CACHE] Erro ao obter stats:", error);
      throw error;
    }
  }, []);

  // Limpa cache expirado
  const cleanup = useCallback(async () => {
    try {
      const response = await api.post("/sla/cache/cleanup");
      console.log(
        `[CACHE] Limpeza concluída: ${response.data.removed} entradas removidas`,
      );
      return response.data;
    } catch (error) {
      console.error("[CACHE] Erro ao limpar cache:", error);
      throw error;
    }
  }, []);

  return {
    warmupCache,
    invalidateChamado,
    invalidateAll,
    getStats,
    cleanup,
  };
}
