import { useEffect, useState } from "react";
import {
  TrendingUp,
  Clock,
  CheckCircle2,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  Loader,
  RefreshCw,
  Calendar,
  X,
} from "lucide-react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useSLACacheManager } from "@/hooks/useSLACacheManager";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Pie,
  PieChart,
  Cell,
  Legend,
} from "recharts";

function Metric({
  label,
  value,
  sub,
  variant,
  icon: Icon,
  trend,
}: {
  label: string;
  value: string;
  sub?: string;
  variant: "orange" | "blue" | "green" | "purple";
  icon: any;
  trend?: "up" | "down";
}) {
  const colorMap = {
    orange: "from-orange-500 to-orange-600",
    blue: "from-blue-500 to-blue-600",
    green: "from-green-500 to-green-600",
    purple: "from-purple-500 to-purple-600",
  };

  return (
    <div className="relative group">
      <div
        className={`absolute -inset-1 bg-gradient-to-r ${colorMap[variant]} rounded-2xl blur-xl opacity-0 group-hover:opacity-30 transition-opacity duration-300`}
      />
      <div
        className={`relative metric-card rounded-2xl bg-gradient-to-br ${colorMap[variant]} text-white p-5 overflow-hidden`}
      >
        {/* Background pattern */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `radial-gradient(circle at 2px 2px, white 1px, transparent 0)`,
            backgroundSize: "32px 32px",
          }}
        />

        <div className="relative space-y-3">
          <div className="flex items-start justify-between">
            <div className="text-xs font-medium opacity-90">{label}</div>
            <Icon className="w-5 h-5 opacity-80" />
          </div>
          <div className="text-3xl font-extrabold leading-none">{value}</div>
          {sub && (
            <div className="flex items-center gap-1.5 text-xs opacity-90">
              {trend &&
                (trend === "up" ? (
                  <ArrowUpRight className="w-3.5 h-3.5" />
                ) : (
                  <ArrowDownRight className="w-3.5 h-3.5" />
                ))}
              <span>{sub}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const COLORS = ["#fa6400", "#334155"];

const colorStyles = {
  orange: "bg-orange-500",
  blue: "bg-blue-500",
  green: "bg-green-500",
  purple: "bg-purple-500",
};

const STATUS_OPTIONS = [
  "Aberto",
  "Em andamento",
  "Em análise",
  "Concluído",
  "Cancelado",
] as const;

export default function Overview() {
  const { warmupCache } = useSLACacheManager();
  const queryClient = useQueryClient();
  const [metrics, setMetrics] = useState<any>(null);
  const [dailyData, setDailyData] = useState<any[]>([]);
  const [weeklyData, setWeeklyData] = useState<any[]>([]);
  const [monthlyData, setMonthlyData] = useState<any[]>([]);
  const [slaData, setSLAData] = useState<{
    dentro_sla: number;
    fora_sla: number;
  }>({ dentro_sla: 0, fora_sla: 0 });
  const [performanceData, setPerformanceData] = useState<{
    tempo_resolucao_medio: string;
    primeira_resposta_media: string;
    taxa_reaberturas: string;
    chamados_backlog: number;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dateRange, setDateRange] = useState<"7d" | "30d" | "90d" | "all">(
    "30d",
  );
  const [showCompleted, setShowCompleted] = useState(true);
  const [selectedStatuses, setSelectedStatuses] = useState<
    typeof STATUS_OPTIONS
  >(["Aberto", "Em andamento", "Concluído"]);

  // Cache de métricas com React Query
  const { data: basicMetricsData, isLoading: basicLoading } = useQuery({
    queryKey: ["metrics-basic"],
    queryFn: async () => {
      const response = await api.get("/metrics/dashboard/basic");
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutos
    gcTime: 30 * 60 * 1000, // 30 minutos (cache persistence)
  });

  const { data: dailyChartData, isLoading: dailyLoading } = useQuery({
    queryKey: ["metrics-daily", selectedStatuses],
    queryFn: async () => {
      const statusQuery =
        selectedStatuses.length > 0
          ? `&statuses=${selectedStatuses.join(",")}`
          : "";
      const response = await api.get(
        `/metrics/chamados-por-dia?dias=7${statusQuery}`,
      );
      return response.data?.dados || [];
    },
    staleTime: 10 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });

  const { data: weeklyChartData, isLoading: weeklyLoading } = useQuery({
    queryKey: ["metrics-weekly", selectedStatuses],
    queryFn: async () => {
      const statusQuery =
        selectedStatuses.length > 0
          ? `&statuses=${selectedStatuses.join(",")}`
          : "";
      const response = await api.get(
        `/metrics/chamados-por-semana?semanas=4${statusQuery}`,
      );
      return response.data?.dados || [];
    },
    staleTime: 10 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });

  const { data: slaMetricsData, isLoading: slaLoading } = useQuery({
    queryKey: ["metrics-sla"],
    queryFn: async () => {
      const response = await api.get("/metrics/dashboard/sla");
      return response.data;
    },
    staleTime: 30 * 60 * 1000, // 30 minutos
    gcTime: 120 * 60 * 1000, // 120 minutos (cache persistence)
  });

  const { data: performanceMetricsData, isLoading: performanceLoading } =
    useQuery({
      queryKey: ["metrics-performance"],
      queryFn: async () => {
        const response = await api.get("/metrics/performance");
        return response.data;
      },
      staleTime: 15 * 60 * 1000,
      gcTime: 60 * 60 * 1000,
    });

  const { data: p90AnalysisData, isLoading: p90Loading } = useQuery({
    queryKey: ["sla-p90-analysis"],
    queryFn: async () => {
      const response = await api.get("/sla/recommendations/p90-analysis");
      return response.data;
    },
    staleTime: 30 * 60 * 1000,
    gcTime: 120 * 60 * 1000,
  });

  const { data: monthlyChartData, isLoading: monthlyLoading } = useQuery({
    queryKey: ["metrics-monthly", dateRange, selectedStatuses],
    queryFn: async () => {
      const statusQuery =
        selectedStatuses.length > 0
          ? `&statuses=${selectedStatuses.join(",")}`
          : "";
      const response = await api.get(
        `/metrics/chamados-por-mes?range=${dateRange}${statusQuery}`,
      );
      return response.data?.dados || [];
    },
    staleTime: 15 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });

  // Atualiza estado local quando dados do React Query chegam
  useEffect(() => {
    if (basicMetricsData) {
      setMetrics(basicMetricsData);
    }
  }, [basicMetricsData]);

  useEffect(() => {
    if (dailyChartData && Array.isArray(dailyChartData)) {
      setDailyData(dailyChartData);
    }
  }, [dailyChartData]);

  useEffect(() => {
    if (weeklyChartData && Array.isArray(weeklyChartData)) {
      setWeeklyData(weeklyChartData);
    }
  }, [weeklyChartData]);

  useEffect(() => {
    if (monthlyChartData && Array.isArray(monthlyChartData)) {
      setMonthlyData(monthlyChartData);
    }
  }, [monthlyChartData]);

  useEffect(() => {
    if (performanceMetricsData) {
      setPerformanceData(performanceMetricsData);
    }
  }, [performanceMetricsData]);

  useEffect(() => {
    if (slaMetricsData) {
      // Merge das métricas de SLA com validação
      setMetrics((prev) => ({
        ...prev,
        sla_compliance_24h: Number(slaMetricsData.sla_compliance_24h ?? 0),
        sla_compliance_mes: Number(slaMetricsData.sla_compliance_mes ?? 0),
        tempo_resposta_24h: slaMetricsData.tempo_resposta_24h ?? "—",
        tempo_resposta_mes: slaMetricsData.tempo_resposta_mes ?? "—",
        total_chamados_mes: Number(slaMetricsData.total_chamados_mes ?? 0),
      }));

      // Atualiza distribuição SLA
      if (slaMetricsData?.sla_distribution) {
        setSLAData({
          dentro_sla: Number(slaMetricsData.sla_distribution.dentro_sla ?? 0),
          fora_sla: Number(slaMetricsData.sla_distribution.fora_sla ?? 0),
        });
      }
    }
  }, [slaMetricsData]);

  const atualizarMetricasMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/sla/recalcular/painel");
      return response.data;
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["metrics-basic"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-sla"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-daily"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-weekly"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-monthly"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-performance"] });
      queryClient.invalidateQueries({ queryKey: ["sla-p90-analysis"] });

      const totalRecalculados = data.total_recalculados || 0;
      const emDia = data.em_dia || 0;
      const vencidos = data.vencidos || 0;

      toast.success(
        `Métricas atualizadas! ${totalRecalculados} chamados recalculados (${emDia} em dia, ${vencidos} vencidos).`,
      );
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.detail || "Erro ao atualizar métricas de SLA",
      );
    },
  });

  // Pré-aquece cache na primeira carga
  useEffect(() => {
    const preWarmCache = async () => {
      try {
        await warmupCache();
      } catch (error) {
        console.warn("Aviso: Pré-aquecimento de cache falhou");
      }
    };
    preWarmCache();
  }, [warmupCache]);

  // Toggle status selection
  const toggleStatus = (status: (typeof STATUS_OPTIONS)[number]) => {
    setSelectedStatuses((prev) =>
      prev.includes(status)
        ? prev.filter((s) => s !== status)
        : [...prev, status],
    );
  };

  // Listener WebSocket para atualizações em tempo real de métricas
  useEffect(() => {
    try {
      const socket = (window as any).__APP_SOCK__;

      if (!socket) {
        console.debug(
          "[Overview] WebSocket não disponível ainda para listener de métricas",
        );
        return;
      }

      const handleMetricsUpdated = () => {
        console.debug(
          "[Overview] Recebido evento metrics:updated, invalidando cache",
        );
        // Invalida todas as queries de métricas para forçar refetch imediato
        queryClient.invalidateQueries({ queryKey: ["metrics-basic"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-daily"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-weekly"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-monthly"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-sla"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-performance"] });
      };

      const handleSLAReset = (data: any) => {
        console.debug(
          "[Overview] Recebido evento sla:reset, invalidando cache de SLA",
          data,
        );
        // Invalida todas as queries quando SLA é resetado
        queryClient.invalidateQueries({ queryKey: ["metrics-basic"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-daily"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-weekly"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-monthly"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-sla"] });
        queryClient.invalidateQueries({ queryKey: ["metrics-performance"] });
        queryClient.invalidateQueries({ queryKey: ["sla-p90-analysis"] });
      };

      socket.on("metrics:updated", handleMetricsUpdated);
      socket.on("sla:reset", handleSLAReset);

      return () => {
        socket.off("metrics:updated", handleMetricsUpdated);
        socket.off("sla:reset", handleSLAReset);
      };
    } catch (error) {
      console.debug("[Overview] Erro ao configurar listener WebSocket:", error);
    }
  }, [queryClient]);

  // Determina se está carregando
  useEffect(() => {
    const allLoading =
      basicLoading ||
      dailyLoading ||
      weeklyLoading ||
      slaLoading ||
      performanceLoading ||
      p90Loading ||
      monthlyLoading;
    setIsLoading(allLoading);
  }, [
    basicLoading,
    dailyLoading,
    weeklyLoading,
    slaLoading,
    performanceLoading,
    p90Loading,
    monthlyLoading,
  ]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Visão Geral</h1>
          <Button
            onClick={() => atualizarMetricasMutation.mutate()}
            disabled={atualizarMetricasMutation.isPending}
            size="sm"
            className="gap-2"
          >
            <RefreshCw
              className={`w-4 h-4 ${atualizarMetricasMutation.isPending ? "animate-spin" : ""}`}
            />
            {atualizarMetricasMutation.isPending
              ? "Atualizando..."
              : "Atualizar Métricas"}
          </Button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="relative group h-32 rounded-2xl bg-muted/50 animate-pulse flex items-center justify-center"
            >
              <Loader className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const comparacao = metrics?.comparacao_ontem || {
    hoje: 0,
    ontem: 0,
    percentual: 0,
    direcao: "up",
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Visão Geral</h1>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-muted-foreground" />
              <Select
                value={dateRange}
                onValueChange={(v) => setDateRange(v as any)}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7d">Últimos 7 dias</SelectItem>
                  <SelectItem value="30d">Últimos 30 dias</SelectItem>
                  <SelectItem value="90d">Últimos 90 dias</SelectItem>
                  <SelectItem value="all">Todos os dados</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => atualizarMetricasMutation.mutate()}
              disabled={atualizarMetricasMutation.isPending}
              size="sm"
              className="gap-2"
            >
              <RefreshCw
                className={`w-4 h-4 ${atualizarMetricasMutation.isPending ? "animate-spin" : ""}`}
              />
              {atualizarMetricasMutation.isPending
                ? "Atualizando..."
                : "Atualizar Métricas"}
            </Button>
          </div>
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="gap-2">
                <span className="text-sm">
                  Status selecionados ({selectedStatuses.length})
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {STATUS_OPTIONS.map((status) => (
                <DropdownMenuCheckboxItem
                  key={status}
                  checked={selectedStatuses.includes(status)}
                  onCheckedChange={() => toggleStatus(status)}
                >
                  {status}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          {selectedStatuses.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                setSelectedStatuses(["Aberto", "Em andamento", "Concluído"])
              }
              className="text-xs"
            >
              Redefinir filtro
            </Button>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric
          label="Chamados hoje"
          value={String(metrics?.chamados_hoje || 0)}
          sub={`${comparacao.percentual >= 0 ? "+" : ""}${comparacao.percentual}% vs ontem`}
          variant="orange"
          icon={TrendingUp}
          trend={comparacao.direcao}
        />
        <Metric
          label="Tempo médio de resposta"
          value={metrics?.tempo_resposta_mes || "—"}
          sub={`Este mês (${metrics?.total_chamados_mes || 0} chamados)`}
          variant="blue"
          icon={Clock}
        />
        <Metric
          label="Conformidade SLA"
          value={`${slaData.dentro_sla > 0 ? Math.round((slaData.dentro_sla / (slaData.dentro_sla + slaData.fora_sla)) * 100) : 0}%`}
          sub={`${slaData.dentro_sla} de ${slaData.dentro_sla + slaData.fora_sla} chamados`}
          variant="green"
          icon={CheckCircle2}
          trend={slaData.dentro_sla > slaData.fora_sla ? "up" : "down"}
        />
        <Metric
          label="Chamados ativos"
          value={String(metrics?.abertos_agora || 0)}
          sub="não concluídos"
          variant="purple"
          icon={AlertCircle}
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-primary/10 to-primary/5 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className="relative card-surface rounded-2xl p-6 border border-border/60">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-lg">Chamados por dia</h3>
              <div className="px-2.5 py-1 bg-primary/10 border border-primary/20 rounded-full">
                <span className="text-xs font-medium text-primary">
                  Última semana
                </span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={dailyData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                  opacity={0.3}
                />
                <XAxis
                  dataKey="dia"
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                />
                <Legend />
                {selectedStatuses.includes("Aberto") && (
                  <Bar
                    dataKey="aberto"
                    fill="#06b6d4"
                    radius={[8, 8, 0, 0]}
                    name="Aberto"
                  />
                )}
                {selectedStatuses.includes("Em andamento") && (
                  <Bar
                    dataKey="em_andamento"
                    fill="#f59e0b"
                    radius={[8, 8, 0, 0]}
                    name="Em andamento"
                  />
                )}
                {selectedStatuses.includes("Em análise") && (
                  <Bar
                    dataKey="em_analise"
                    fill="#8b5cf6"
                    radius={[8, 8, 0, 0]}
                    name="Em análise"
                  />
                )}
                {selectedStatuses.includes("Concluído") && (
                  <Bar
                    dataKey="concluido"
                    fill="#10b981"
                    radius={[8, 8, 0, 0]}
                    name="Concluído"
                  />
                )}
                {selectedStatuses.includes("Cancelado") && (
                  <Bar
                    dataKey="cancelado"
                    fill="#ef4444"
                    radius={[8, 8, 0, 0]}
                    name="Cancelado"
                  />
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-primary/10 to-primary/5 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className="relative card-surface rounded-2xl p-6 border border-border/60">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-lg">Chamados por semana</h3>
              <div className="px-2.5 py-1 bg-primary/10 border border-primary/20 rounded-full">
                <span className="text-xs font-medium text-primary">
                  Último mês
                </span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={weeklyData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                  opacity={0.3}
                />
                <XAxis
                  dataKey="semana"
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                />
                <Legend />
                {selectedStatuses.includes("Aberto") && (
                  <Bar
                    dataKey="aberto"
                    fill="#06b6d4"
                    radius={[8, 8, 0, 0]}
                    name="Aberto"
                  />
                )}
                {selectedStatuses.includes("Em andamento") && (
                  <Bar
                    dataKey="em_andamento"
                    fill="#f59e0b"
                    radius={[8, 8, 0, 0]}
                    name="Em andamento"
                  />
                )}
                {selectedStatuses.includes("Em análise") && (
                  <Bar
                    dataKey="em_analise"
                    fill="#8b5cf6"
                    radius={[8, 8, 0, 0]}
                    name="Em análise"
                  />
                )}
                {selectedStatuses.includes("Concluído") && (
                  <Bar
                    dataKey="concluido"
                    fill="#10b981"
                    radius={[8, 8, 0, 0]}
                    name="Concluído"
                  />
                )}
                {selectedStatuses.includes("Cancelado") && (
                  <Bar
                    dataKey="cancelado"
                    fill="#ef4444"
                    radius={[8, 8, 0, 0]}
                    name="Cancelado"
                  />
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Monthly Chart */}
      <div className="relative group">
        <div className="absolute -inset-1 bg-gradient-to-r from-primary/10 to-primary/5 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
        <div className="relative card-surface rounded-2xl p-6 border border-border/60">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-lg">Chamados por Mês</h3>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={monthlyData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
              />
              <XAxis
                dataKey="mes"
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
              />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {selectedStatuses.includes("Aberto") && (
                <Bar
                  dataKey="aberto"
                  fill="#06b6d4"
                  radius={[8, 8, 0, 0]}
                  name="Aberto"
                />
              )}
              {selectedStatuses.includes("Em andamento") && (
                <Bar
                  dataKey="em_andamento"
                  fill="#f59e0b"
                  radius={[8, 8, 0, 0]}
                  name="Em andamento"
                />
              )}
              {selectedStatuses.includes("Em análise") && (
                <Bar
                  dataKey="em_analise"
                  fill="#8b5cf6"
                  radius={[8, 8, 0, 0]}
                  name="Em análise"
                />
              )}
              {selectedStatuses.includes("Concluído") && (
                <Bar
                  dataKey="concluido"
                  fill="#10b981"
                  radius={[8, 8, 0, 0]}
                  name="Concluído"
                />
              )}
              {selectedStatuses.includes("Cancelado") && (
                <Bar
                  dataKey="cancelado"
                  fill="#ef4444"
                  radius={[8, 8, 0, 0]}
                  name="Cancelado"
                />
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2 - SLA Distribution and P90 Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="relative group lg:col-span-1">
          <div className="absolute -inset-1 bg-gradient-to-r from-primary/10 to-primary/5 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className="relative card-surface rounded-2xl p-6 border border-border/60">
            <h3 className="font-semibold text-lg mb-4">Distribuição SLA</h3>
            <div className="flex items-center justify-center">
              {slaData.dentro_sla === 0 && slaData.fora_sla === 0 ? (
                <div className="h-[220px] flex items-center justify-center text-muted-foreground">
                  Sem dados de SLA
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={[
                        { name: "Dentro SLA", value: slaData.dentro_sla },
                        { name: "Fora SLA", value: slaData.fora_sla },
                      ]}
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {[
                        { name: "Dentro SLA", value: slaData.dentro_sla },
                        { name: "Fora SLA", value: slaData.fora_sla },
                      ].map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={COLORS[index % COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="flex items-center justify-center gap-6 mt-4">
              {[
                { name: "Dentro SLA", value: slaData.dentro_sla },
                { name: "Fora SLA", value: slaData.fora_sla },
              ].map((item, index) => {
                const total = slaData.dentro_sla + slaData.fora_sla;
                const percentage =
                  total > 0 ? Math.round((item.value / total) * 100) : 0;
                return (
                  <div key={index} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COLORS[index] }}
                    />
                    <span className="text-sm text-muted-foreground">
                      {item.name}:{" "}
                      <span className="font-semibold text-foreground">
                        {percentage}%
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="relative group lg:col-span-2">
          <div className="absolute -inset-1 bg-gradient-to-r from-primary/10 to-primary/5 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className="relative card-surface rounded-2xl p-6 border border-border/60">
            <h3 className="font-semibold text-lg mb-4">
              P90 Recomendado vs SLA Atual
            </h3>
            <div className="space-y-3">
              {p90Loading ? (
                <div className="text-muted-foreground text-center py-4">
                  <Loader className="w-4 h-4 animate-spin mx-auto" />
                </div>
              ) : !p90AnalysisData?.prioridades ||
                Object.keys(p90AnalysisData.prioridades).length === 0 ? (
                <div className="text-muted-foreground text-center py-4 text-sm">
                  Dados insuficientes para análise
                </div>
              ) : (
                Object.entries(p90AnalysisData.prioridades).map(
                  ([prioridade, data]: [string, any]) => (
                    <div
                      key={prioridade}
                      className="p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold">
                          {prioridade}
                        </span>
                        <span
                          className={`text-xs font-bold px-2 py-1 rounded-full ${
                            data.melhoria > 0
                              ? "bg-green-500/20 text-green-700 dark:text-green-400"
                              : "bg-gray-500/20 text-gray-700 dark:text-gray-400"
                          }`}
                        >
                          +{data.melhoria}%
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mb-2">
                        {data.chamados_analisados} chamados • Min:{" "}
                        {data.tempo_minimo}h • Médio: {data.tempo_medio}h • Máx:{" "}
                        {data.tempo_maximo}h
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <div className="text-muted-foreground">SLA Atual</div>
                          <div className="font-semibold">{data.sla_atual}h</div>
                          <div className="text-xs text-muted-foreground">
                            {data.conformidade_atual}% ok
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">P90</div>
                          <div className="font-semibold">
                            {data.p90.toFixed(1)}h
                          </div>
                          <div className="text-xs text-muted-foreground">-</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">
                            Recomendado
                          </div>
                          <div className="font-semibold">
                            {data.p90_recomendado}h
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {data.conformidade_com_p90}% ok
                          </div>
                        </div>
                      </div>
                    </div>
                  ),
                )
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
