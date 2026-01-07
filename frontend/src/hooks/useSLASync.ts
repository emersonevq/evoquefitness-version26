import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface SLASyncStats {
  total_recalculados: number;
  em_dia: number;
  vencidos: number;
  em_andamento: number;
  congelados: number;
  erros: number;
}

/**
 * Hook para recalcular SLAs quando necessário.
 * Não faz chamadas automáticas, apenas fornece a função de recálculo.
 */
export function useSLASync() {
  const queryClient = useQueryClient();

  const {
    mutate,
    isPending: isLoading,
    data: stats,
  } = useMutation({
    mutationFn: async () => {
      const response = await api.post("/sla/recalcular/painel");
      return response.data as SLASyncStats;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-sync"] });
    },
  });

  const refetch = useCallback(() => {
    mutate();
  }, [mutate]);

  return {
    stats,
    isLoading,
    refetch,
  };
}

/**
 * Hook para sincronizar todos os chamados existentes com a tabela de SLA.
 * Deve ser executado uma única vez ou para revalidação completa.
 */
export function useSLASyncAll() {
  const queryClient = useQueryClient();

  const {
    mutate,
    isPending,
    data: stats,
  } = useMutation({
    mutationFn: async () => {
      const response = await api.post("/sla/sync/todos-chamados");
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-sync-all"] });
    },
  });

  return {
    stats,
    sync: mutate,
    isPending,
  };
}
