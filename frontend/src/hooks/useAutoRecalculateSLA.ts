import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useSLACacheManager } from "./useSLACacheManager";

interface RecalculateStats {
  total_recalculados: number;
  em_dia: number;
  vencidos: number;
  em_andamento: number;
  congelados: number;
  erros: number;
}

/**
 * Hook para recalcular SLA de forma inteligente com cache
 *
 * Estratégia:
 * 1. Ao abrir o painel, tenta preaquecer o cache
 * 2. Se o cache está vazio/expirado, força recalcular
 * 3. Invalida caches relacionados após recálculo
 */
export function useAutoRecalculateSLA() {
  const queryClient = useQueryClient();
  const { warmupCache } = useSLACacheManager();

  const mutation = useMutation({
    mutationFn: async () => {
      // Tenta preaquecer primeiro (mais rápido se cache está quente)
      try {
        await warmupCache();
        console.log("[SLA] Cache pré-aquecido com sucesso");
      } catch (warmupError) {
        console.log("[SLA] Warmup falhou, forçando recálculo...");
        // Se warmup falha, força recalcular completo
        const response = await api.post("/sla/recalcular/painel");
        return response.data as RecalculateStats;
      }

      // Se warmup foi bem-sucedido, retorna stats vazios
      return {
        total_recalculados: 0,
        em_dia: 0,
        vencidos: 0,
        em_andamento: 0,
        congelados: 0,
        erros: 0,
      };
    },
    onSuccess: () => {
      // Invalida queries de SLA/métricas para atualizar UI
      queryClient.invalidateQueries({ queryKey: ["sla-status-realtime"] });
      queryClient.invalidateQueries({ queryKey: ["sla-status"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["sla-"] });

      console.log("[SLA] SLA recalculado e cache invalidado com sucesso");
    },
    onError: (error) => {
      console.error("[SLA] Erro ao recalcular SLA:", error);
    },
  });

  // Dispara warmup automaticamente ao montar o componente
  useEffect(() => {
    console.log(
      "[SLA] Painel administrativo aberto, iniciando cache warmup...",
    );
    mutation.mutate();
  }, []); // Executa apenas uma vez ao montar

  return {
    stats: mutation.data,
    isLoading: mutation.isPending,
    error: mutation.error,
    recalculate: mutation.mutate,
  };
}
