import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface SLAStatus {
  chamado_id: number;
  prioridade: string;
  status: string;
  tempo_decorrido_horas: number;
  tempo_resposta_limite_horas: number;
  tempo_resolucao_limite_horas: number;
  tempo_resposta_horas: number;
  tempo_resposta_status:
    | "ok"
    | "vencido"
    | "em_andamento"
    | "congelado"
    | "sem_configuracao";
  tempo_resolucao_horas: number;
  tempo_resolucao_status:
    | "ok"
    | "vencido"
    | "em_andamento"
    | "congelado"
    | "sem_configuracao";
  data_abertura: string | null;
  data_primeira_resposta: string | null;
  data_conclusao: string | null;
}

export function useSLAStatus(chamadoId: number) {
  return useQuery({
    queryKey: ["sla-status", chamadoId],
    queryFn: async () => {
      const response = await api.get(`/sla/chamado/${chamadoId}/status`);
      return response.data as SLAStatus;
    },
    enabled: !!chamadoId,
    refetchInterval: 10000,
    staleTime: 9000,
  });
}

export type { SLAStatus };
