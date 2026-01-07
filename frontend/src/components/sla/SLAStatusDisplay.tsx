import { AlertCircle, CheckCircle2, Clock, Loader } from "lucide-react";
import { useRealTimeSLA } from "@/hooks/useRealTimeSLA";

interface SLAStatusDisplayProps {
  chamadoId: number;
}

export function SLAStatusDisplay({ chamadoId }: SLAStatusDisplayProps) {
  const { data, isLoading, isFetching } = useRealTimeSLA(chamadoId);

  if (isLoading) {
    return (
      <div className="rounded-lg border bg-card p-5 space-y-4 h-fit">
        <div className="flex items-center justify-center py-8">
          <Loader className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-lg border bg-card p-5 space-y-4 h-fit">
        <p className="text-sm text-muted-foreground">Sem dados de SLA</p>
      </div>
    );
  }

  const formatHours = (hours: number | null | undefined) => {
    if (hours === null || hours === undefined) {
      return "—";
    }
    if (hours < 1) {
      return `${Math.round(hours * 60)}m`;
    }
    if (hours % 1 === 0) {
      return `${Math.round(hours)}h`;
    }
    return `${hours.toFixed(1)}h`;
  };

  const getStatusColor = (
    status:
      | "ok"
      | "vencido"
      | "em_andamento"
      | "congelado"
      | "sem_configuracao",
  ) => {
    switch (status) {
      case "ok":
        return "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800";
      case "vencido":
        return "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800";
      case "em_andamento":
        return "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800";
      case "congelado":
        return "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800";
      default:
        return "bg-gray-100 dark:bg-gray-900/30 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-800";
    }
  };

  const getStatusIcon = (
    status:
      | "ok"
      | "vencido"
      | "em_andamento"
      | "congelado"
      | "sem_configuracao",
  ) => {
    switch (status) {
      case "ok":
        return CheckCircle2;
      case "vencido":
        return AlertCircle;
      default:
        return Clock;
    }
  };

  const getStatusLabel = (
    status:
      | "ok"
      | "vencido"
      | "em_andamento"
      | "congelado"
      | "sem_configuracao",
  ) => {
    switch (status) {
      case "ok":
        return "Dentro do SLA";
      case "vencido":
        return "SLA Vencido";
      case "em_andamento":
        return "Em Andamento";
      case "congelado":
        return "Congelado";
      default:
        return "Sem Configuração";
    }
  };

  const tempoResposta = data.tempo_resposta_horas_live;
  const tempoResolucao = data.tempo_resolucao_horas_live;
  const statusResposta = data.tempo_resposta_status;
  const statusResolucao = data.tempo_resolucao_status;

  return (
    <div className="rounded-lg border bg-card p-5 space-y-4 h-fit">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg">Status de SLA</h3>
        {isFetching && (
          <Loader className="w-4 h-4 animate-spin text-muted-foreground" />
        )}
      </div>

      <div className="space-y-1 text-sm">
        <p className="text-muted-foreground">Prioridade:</p>
        <p className="font-semibold">{data.prioridade || "—"}</p>
      </div>

      <div className="space-y-3 border-t pt-4">
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Tempo de Resposta</h4>
          <div
            className={`border rounded-lg p-3 space-y-2 ${getStatusColor(statusResposta)}`}
          >
            <div className="flex items-center gap-2">
              {(() => {
                const Icon = getStatusIcon(statusResposta);
                return <Icon className="w-4 h-4 flex-shrink-0" />;
              })()}
              <span className="text-sm font-medium">
                {getStatusLabel(statusResposta)}
              </span>
            </div>
            <div className="text-xs space-y-1 ml-6">
              <div className="flex justify-between">
                <span>Decorrido:</span>
                <span className="font-semibold">
                  {formatHours(tempoResposta)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Limite:</span>
                <span className="font-semibold">
                  {formatHours(data.tempo_resposta_limite_horas)}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-sm font-medium">Tempo de Resolução</h4>
          <div
            className={`border rounded-lg p-3 space-y-2 ${getStatusColor(statusResolucao)}`}
          >
            <div className="flex items-center gap-2">
              {(() => {
                const Icon = getStatusIcon(statusResolucao);
                return <Icon className="w-4 h-4 flex-shrink-0" />;
              })()}
              <span className="text-sm font-medium">
                {getStatusLabel(statusResolucao)}
              </span>
            </div>
            <div className="text-xs space-y-1 ml-6">
              <div className="flex justify-between">
                <span>Decorrido:</span>
                <span className="font-semibold">
                  {formatHours(tempoResolucao)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Limite:</span>
                <span className="font-semibold">
                  {formatHours(data.tempo_resolucao_limite_horas)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
