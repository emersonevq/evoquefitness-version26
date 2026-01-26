import {
  AlertCircle,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Loader,
} from "lucide-react";
import { useSLAStatus, SLAStatus } from "@/hooks/useSLAStatus";

interface SLAStatusDisplayProps {
  chamadoId: number;
}

export function SLAStatusDisplay({ chamadoId }: SLAStatusDisplayProps) {
  const { data, isLoading, isFetching } = useSLAStatus(chamadoId);

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

  const formatHours = (hours: number | null | undefined): string => {
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

  const getStatusColor = (status: string): string => {
    switch (status) {
      case "cumprido":
        return "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800";
      case "violado":
        return "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800";
      case "dentro_prazo":
        return "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800";
      case "proximo_vencer":
        return "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800";
      case "vencido_ativo":
        return "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800";
      case "pausado":
        return "bg-gray-100 dark:bg-gray-900/30 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-800";
      case "sem_sla":
        return "bg-gray-100 dark:bg-gray-900/30 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-800";
      default:
        return "bg-gray-100 dark:bg-gray-900/30 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-800";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "cumprido":
      case "dentro_prazo":
        return CheckCircle2;
      case "violado":
      case "vencido_ativo":
        return AlertCircle;
      case "proximo_vencer":
        return AlertTriangle;
      default:
        return Clock;
    }
  };

  const getStatusLabel = (status: string): string => {
    switch (status) {
      case "cumprido":
        return "Cumprido";
      case "violado":
        return "Violado";
      case "dentro_prazo":
        return "Dentro do Prazo";
      case "proximo_vencer":
        return "Próximo de Vencer";
      case "vencido_ativo":
        return "Vencido";
      case "pausado":
        return "Pausado";
      case "sem_sla":
        return "Sem SLA";
      default:
        return "Desconhecido";
    }
  };

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
        {/* Métrica de Resposta */}
        {data.resposta_metric ? (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Tempo de Resposta</h4>
            <div
              className={`border rounded-lg p-3 space-y-2 ${getStatusColor(data.resposta_metric.status)}`}
            >
              <div className="flex items-center gap-2">
                {(() => {
                  const Icon = getStatusIcon(data.resposta_metric.status);
                  return <Icon className="w-4 h-4 flex-shrink-0" />;
                })()}
                <span className="text-sm font-medium">
                  {getStatusLabel(data.resposta_metric.status)}
                </span>
              </div>
              <div className="text-xs space-y-1 ml-6">
                <div className="flex justify-between">
                  <span>Decorrido:</span>
                  <span className="font-semibold">
                    {formatHours(data.resposta_metric.tempo_decorrido_horas)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Limite:</span>
                  <span className="font-semibold">
                    {formatHours(data.resposta_metric.tempo_limite_horas)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Percentual:</span>
                  <span className="font-semibold">
                    {Math.round(data.resposta_metric.percentual_consumido)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {/* Métrica de Resolução */}
        {data.resolucao_metric ? (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Tempo de Resolução</h4>
            <div
              className={`border rounded-lg p-3 space-y-2 ${getStatusColor(data.resolucao_metric.status)}`}
            >
              <div className="flex items-center gap-2">
                {(() => {
                  const Icon = getStatusIcon(data.resolucao_metric.status);
                  return <Icon className="w-4 h-4 flex-shrink-0" />;
                })()}
                <span className="text-sm font-medium">
                  {getStatusLabel(data.resolucao_metric.status)}
                </span>
              </div>
              <div className="text-xs space-y-1 ml-6">
                <div className="flex justify-between">
                  <span>Decorrido:</span>
                  <span className="font-semibold">
                    {formatHours(data.resolucao_metric.tempo_decorrido_horas)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Limite:</span>
                  <span className="font-semibold">
                    {formatHours(data.resolucao_metric.tempo_limite_horas)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Percentual:</span>
                  <span className="font-semibold">
                    {Math.round(data.resolucao_metric.percentual_consumido)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {/* Status Geral */}
        <div className="space-y-2 border-t pt-4">
          <h4 className="text-sm font-medium">Status Geral</h4>
          <div
            className={`border rounded-lg p-3 ${getStatusColor(data.status_geral)}`}
          >
            <div className="flex items-center gap-2">
              {(() => {
                const Icon = getStatusIcon(data.status_geral);
                return <Icon className="w-5 h-5 flex-shrink-0" />;
              })()}
              <span className="font-semibold">
                {getStatusLabel(data.status_geral)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
