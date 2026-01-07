import { useEffect, useState } from "react";
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

interface RealTimeSLAStatus extends SLAStatus {
  tempo_resposta_horas_live: number;
  tempo_resolucao_horas_live: number;
}

export function useRealTimeSLA(chamadoId: number) {
  const [liveData, setLiveData] = useState<RealTimeSLAStatus | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number>(0);

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["sla-status-realtime", chamadoId],
    queryFn: async () => {
      const response = await api.get(`/sla/chamado/${chamadoId}/status`);
      return response.data as SLAStatus;
    },
    enabled: !!chamadoId,
    refetchInterval: 10000,
    staleTime: 9000,
  });

  useEffect(() => {
    if (!data) return;

    const now = Date.now();
    setLastUpdate(now);

    const timer = setInterval(() => {
      setLiveData((prev) => {
        if (!prev) return prev;

        const elapsedSeconds = (Date.now() - now) / 1000;
        const elapsedHours = elapsedSeconds / 3600;

        return {
          ...prev,
          tempo_resposta_horas_live: prev.tempo_resposta_horas + elapsedHours,
          tempo_resolucao_horas_live: prev.tempo_resolucao_horas + elapsedHours,
        };
      });
    }, 1000);

    const initialLive: RealTimeSLAStatus = {
      ...data,
      tempo_resposta_horas_live: data.tempo_resposta_horas,
      tempo_resolucao_horas_live: data.tempo_resolucao_horas,
    };

    setLiveData(initialLive);

    return () => clearInterval(timer);
  }, [data]);

  return {
    data: liveData,
    isLoading,
    isFetching,
    refetch,
  };
}
