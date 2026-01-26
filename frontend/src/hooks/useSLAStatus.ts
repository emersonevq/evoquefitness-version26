import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface SLAMetric {
  tempo_decorrido_horas: number;
  tempo_limite_horas: number;
  percentual_consumido: number;
  status:
    | "cumprido"
    | "violado"
    | "dentro_prazo"
    | "proximo_vencer"
    | "vencido_ativo"
    | "pausado"
    | "sem_sla";
  data_inicio: string | null;
  data_fim: string | null;
}

export interface SLAStatus {
  chamado_id: number;
  prioridade: string;
  status_chamado: string;
  resposta_metric: SLAMetric | null;
  resolucao_metric: SLAMetric | null;
  status_geral:
    | "cumprido"
    | "violado"
    | "dentro_prazo"
    | "proximo_vencer"
    | "vencido_ativo"
    | "pausado"
    | "sem_sla";
  data_abertura: string | null;
  data_primeira_resposta: string | null;
  data_conclusao: string | null;
}

/**
 * Hook para obter status de SLA de um chamado
 * Utiliza o servidor como fonte de verdade para tempo ao vivo
 * Refetch automático a cada 10 segundos
 */
export function useSLAStatus(chamadoId: number) {
  return useQuery({
    queryKey: ["sla-status", chamadoId],
    queryFn: async () => {
      try {
        const response = await api.get<SLAStatus>(
          `/sla/chamado/${chamadoId}/status`,
        );
        return response.data;
      } catch (error) {
        console.error(
          `[SLA] Erro ao buscar status do chamado #${chamadoId}:`,
          error,
        );
        throw error;
      }
    },
    enabled: !!chamadoId,
    refetchInterval: 10000, // Atualiza a cada 10 segundos
    staleTime: 9000, // Cache válido por 9 segundos
    retry: 2, // Tenta novamente 2 vezes antes de falhar
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}
