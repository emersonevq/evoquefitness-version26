import { AlertCircle, CheckCircle2, Clock } from "lucide-react";

interface SLAStatusBadgeProps {
  status: "ok" | "vencido" | "em_andamento" | "congelado" | "sem_configuracao";
  tempoDecorrido: number;
  limiteHoras: number;
  tipo?: "resposta" | "resolucao";
}

export function SLAStatusBadge({
  status,
  tempoDecorrido,
  limiteHoras,
  tipo = "resolucao",
}: SLAStatusBadgeProps) {
  const statusConfig = {
    ok: {
      bg: "bg-green-100 dark:bg-green-900/30",
      text: "text-green-700 dark:text-green-300",
      border: "border-green-200 dark:border-green-800",
      icon: CheckCircle2,
      label: "Dentro do SLA",
    },
    vencido: {
      bg: "bg-red-100 dark:bg-red-900/30",
      text: "text-red-700 dark:text-red-300",
      border: "border-red-200 dark:border-red-800",
      icon: AlertCircle,
      label: "SLA Vencido",
    },
    em_andamento: {
      bg: "bg-amber-100 dark:bg-amber-900/30",
      text: "text-amber-700 dark:text-amber-300",
      border: "border-amber-200 dark:border-amber-800",
      icon: Clock,
      label: "Em Andamento",
    },
    congelado: {
      bg: "bg-blue-100 dark:bg-blue-900/30",
      text: "text-blue-700 dark:text-blue-300",
      border: "border-blue-200 dark:border-blue-800",
      icon: Clock,
      label: "Congelado",
    },
    sem_configuracao: {
      bg: "bg-gray-100 dark:bg-gray-900/30",
      text: "text-gray-700 dark:text-gray-300",
      border: "border-gray-200 dark:border-gray-800",
      icon: Clock,
      label: "Sem Configuração",
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  const formatHours = (hours: number) => {
    if (hours < 1) {
      return `${Math.round(hours * 60)}m`;
    }
    if (hours % 1 === 0) {
      return `${Math.round(hours)}h`;
    }
    return `${hours.toFixed(1)}h`;
  };

  return (
    <div
      className={`${config.bg} ${config.text} ${config.border} border rounded-lg p-3 space-y-2`}
    >
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 flex-shrink-0" />
        <span className="text-sm font-medium">{config.label}</span>
      </div>
      <div className="text-xs space-y-1 ml-6">
        <div className="flex justify-between">
          <span>Tempo Decorrido:</span>
          <span className="font-semibold">{formatHours(tempoDecorrido)}</span>
        </div>
        <div className="flex justify-between">
          <span>Limite SLA:</span>
          <span className="font-semibold">{formatHours(limiteHoras)}</span>
        </div>
        {status === "vencido" && (
          <div className="flex justify-between mt-2 pt-2 border-t opacity-75">
            <span>Excesso:</span>
            <span className="font-semibold">
              +{formatHours(tempoDecorrido - limiteHoras)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

interface SLAStatusOverviewProps {
  chamadoId: number;
  prioridade: string;
  statusResposta:
    | "ok"
    | "vencido"
    | "em_andamento"
    | "congelado"
    | "sem_configuracao";
  statusResolucao:
    | "ok"
    | "vencido"
    | "em_andamento"
    | "congelado"
    | "sem_configuracao";
  tempoRepostagem: number;
  tempoResolucao: number;
  limiteResposta: number;
  limiteResolucao: number;
}

export function SLAStatusOverview({
  prioridade,
  statusResposta,
  statusResolucao,
  tempoRepostagem,
  tempoResolucao,
  limiteResposta,
  limiteResolucao,
}: SLAStatusOverviewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold mb-2">
          Nível de Prioridade: {prioridade}
        </h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SLAStatusBadge
          status={statusResposta}
          tempoDecorrido={tempoRepostagem}
          limiteHoras={limiteResposta}
          tipo="resposta"
        />
        <SLAStatusBadge
          status={statusResolucao}
          tempoDecorrido={tempoResolucao}
          limiteHoras={limiteResolucao}
          tipo="resolucao"
        />
      </div>
    </div>
  );
}
