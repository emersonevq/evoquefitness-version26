import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Trash2,
  Plus,
  Edit2,
  RefreshCw,
  Grid3x3,
  List,
  Clock,
  Calendar,
  Package,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface SLAConfig {
  id: number;
  prioridade: string;
  tempo_resposta_horas: number;
  tempo_resolucao_horas: number;
  descricao: string | null;
  ativo: boolean;
  criado_em: string | null;
  atualizado_em: string | null;
}

interface BusinessHours {
  id: number;
  dia_semana: number;
  hora_inicio: string;
  hora_fim: string;
  ativo: boolean;
  criado_em: string | null;
  atualizado_em: string | null;
}

interface Feriado {
  id: number;
  data: string;
  nome: string;
  descricao: string | null;
  ativo: boolean;
  criado_em: string | null;
  atualizado_em: string | null;
}

const DIAS_SEMANA = [
  { id: 0, label: "Segunda-feira" },
  { id: 1, label: "Terça-feira" },
  { id: 2, label: "Quarta-feira" },
  { id: 3, label: "Quinta-feira" },
  { id: 4, label: "Sexta-feira" },
  { id: 5, label: "Sábado" },
  { id: 6, label: "Domingo" },
];

function SLAConfigCard({
  config,
  onEdit,
  onDelete,
}: {
  config: SLAConfig;
  onEdit: (config: SLAConfig) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-card overflow-hidden hover:shadow-md hover:border-primary/20 transition-all">
      <div className="px-4 py-3 border-b border-border/60 bg-muted/30 flex items-center justify-between">
        <div className="font-semibold text-sm text-primary">
          {config.prioridade}
        </div>
        {config.descricao && (
          <span className="text-xs text-muted-foreground">
            {config.descricao}
          </span>
        )}
      </div>
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Resposta
            </div>
            <div className="text-lg font-semibold">
              {config.tempo_resposta_horas}h
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Resolução
            </div>
            <div className="text-lg font-semibold">
              {config.tempo_resolucao_horas}h
            </div>
          </div>
        </div>
        <div className="pt-3 border-t border-border/40 flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onEdit(config)}
            className="flex-1 h-8 text-xs"
          >
            <Edit2 className="w-3.5 h-3.5 mr-1" />
            Editar
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => onDelete(config.id)}
            className="flex-1 h-8 text-xs"
          >
            <Trash2 className="w-3.5 h-3.5 mr-1" />
            Remover
          </Button>
        </div>
      </div>
    </div>
  );
}

export function SLA() {
  const queryClient = useQueryClient();
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showHoursDialog, setShowHoursDialog] = useState(false);
  const [showHolidayDialog, setShowHolidayDialog] = useState(false);
  const [editingConfig, setEditingConfig] = useState<SLAConfig | null>(null);
  const [editingHours, setEditingHours] = useState<BusinessHours | null>(null);
  const [editingFeriado, setEditingFeriado] = useState<Feriado | null>(null);
  const [configViewMode, setConfigViewMode] = useState<"grid" | "list">("grid");

  const [formData, setFormData] = useState({
    prioridade: "",
    tempo_resposta_horas: 2,
    tempo_resolucao_horas: 8,
    descricao: "",
  });

  const [hoursData, setHoursData] = useState({
    dia_semana: 0,
    hora_inicio: "08:00",
    hora_fim: "18:00",
  });

  const [feriadoData, setFeriadoData] = useState({
    data: new Date().toISOString().split("T")[0],
    nome: "",
    descricao: "",
  });

  const { data: configs = [], isLoading: configsLoading } = useQuery({
    queryKey: ["sla-config"],
    queryFn: async () => {
      const response = await api.get("/sla/config");
      return response.data;
    },
  });

  const { data: businessHours = [], isLoading: hoursLoading } = useQuery({
    queryKey: ["sla-business-hours"],
    queryFn: async () => {
      const response = await api.get("/sla/business-hours");
      return response.data;
    },
  });

  const { data: feriados = [], isLoading: feriadosLoading } = useQuery({
    queryKey: ["sla-feriados"],
    queryFn: async () => {
      const response = await api.get("/sla/feriados");
      return response.data;
    },
  });

  const createConfigMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const response = await api.post("/sla/config", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-config"] });
      setShowConfigDialog(false);
      setFormData({
        prioridade: "",
        tempo_resposta_horas: 2,
        tempo_resolucao_horas: 8,
        descricao: "",
      });
      toast.success("Configuração de SLA criada com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao criar configuração");
    },
  });

  const updateConfigMutation = useMutation({
    mutationFn: async (data: {
      id: number;
      updates: Partial<typeof formData>;
    }) => {
      const response = await api.patch(`/sla/config/${data.id}`, data.updates);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-config"] });
      setShowConfigDialog(false);
      setEditingConfig(null);
      setFormData({
        prioridade: "",
        tempo_resposta_horas: 2,
        tempo_resolucao_horas: 8,
        descricao: "",
      });
      toast.success("Configuração atualizada com sucesso");
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.detail || "Erro ao atualizar configuração",
      );
    },
  });

  const deleteConfigMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/sla/config/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-config"] });
      toast.success("Configuração removida com sucesso");
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.detail || "Erro ao remover configuração",
      );
    },
  });

  const createHoursMutation = useMutation({
    mutationFn: async (data: typeof hoursData) => {
      const response = await api.post("/sla/business-hours", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-business-hours"] });
      setShowHoursDialog(false);
      setHoursData({
        dia_semana: 0,
        hora_inicio: "08:00",
        hora_fim: "18:00",
      });
      toast.success("Horário comercial adicionado com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao adicionar horário");
    },
  });

  const updateHoursMutation = useMutation({
    mutationFn: async (data: { id: number; updates: typeof hoursData }) => {
      const response = await api.patch(
        `/sla/business-hours/${data.id}`,
        data.updates,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-business-hours"] });
      setShowHoursDialog(false);
      setEditingHours(null);
      setHoursData({
        dia_semana: 0,
        hora_inicio: "08:00",
        hora_fim: "18:00",
      });
      toast.success("Horário atualizado com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao atualizar horário");
    },
  });

  const deleteHoursMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/sla/business-hours/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-business-hours"] });
      toast.success("Horário removido com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao remover horário");
    },
  });

  const createFeriadoMutation = useMutation({
    mutationFn: async (data: typeof feriadoData) => {
      const response = await api.post("/sla/feriados", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-feriados"] });
      setShowHolidayDialog(false);
      setFeriadoData({
        data: new Date().toISOString().split("T")[0],
        nome: "",
        descricao: "",
      });
      toast.success("Feriado adicionado com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao adicionar feriado");
    },
  });

  const updateFeriadoMutation = useMutation({
    mutationFn: async (data: {
      id: number;
      updates: Omit<typeof feriadoData, "data">;
    }) => {
      const response = await api.patch(
        `/sla/feriados/${data.id}`,
        data.updates,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-feriados"] });
      setShowHolidayDialog(false);
      setEditingFeriado(null);
      setFeriadoData({
        data: new Date().toISOString().split("T")[0],
        nome: "",
        descricao: "",
      });
      toast.success("Feriado atualizado com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao atualizar feriado");
    },
  });

  const deleteFeriadoMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/sla/feriados/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sla-feriados"] });
      toast.success("Feriado removido com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao remover feriado");
    },
  });

  const sincronizarProblemasMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/problemas/sincronizar/sla");
      return response.data;
    },
    onSuccess: (data: any) => {
      const stats = data.estatisticas || {};
      toast.success(
        `${stats.sincronizados || 0} problema(s) sincronizado(s) com SLA`,
      );
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.detail || "Erro ao sincronizar problemas",
      );
    },
  });

  const zerarCacheMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/sla/reset-and-recalculate");
      return response.data;
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["sla-config"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-basic"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-sla"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-daily"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-weekly"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-performance"] });
      toast.success(
        "SLA foi completamente zerado! Próximos cálculos começarão a partir de agora.",
      );
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao zerar SLA");
    },
  });

  const handleAddConfig = () => {
    setEditingConfig(null);
    setFormData({
      prioridade: "",
      tempo_resposta_horas: 2,
      tempo_resolucao_horas: 8,
      descricao: "",
    });
    setShowConfigDialog(true);
  };

  const handleEditConfig = (config: SLAConfig) => {
    setEditingConfig(config);
    setFormData({
      prioridade: config.prioridade,
      tempo_resposta_horas: config.tempo_resposta_horas,
      tempo_resolucao_horas: config.tempo_resolucao_horas,
      descricao: config.descricao || "",
    });
    setShowConfigDialog(true);
  };

  const handleSaveConfig = () => {
    if (!formData.prioridade) {
      toast.error("Preencha o campo de prioridade");
      return;
    }

    if (editingConfig) {
      updateConfigMutation.mutate({
        id: editingConfig.id,
        updates: {
          tempo_resposta_horas: formData.tempo_resposta_horas,
          tempo_resolucao_horas: formData.tempo_resolucao_horas,
          descricao: formData.descricao,
        },
      });
    } else {
      createConfigMutation.mutate(formData);
    }
  };

  const handleAddHours = () => {
    setEditingHours(null);
    // Encontra o primeiro dia sem horário configurado
    let firstAvailableDay = 0;
    for (let i = 0; i < DIAS_SEMANA.length; i++) {
      const exists = businessHours.some(
        (h: BusinessHours) => h.dia_semana === i,
      );
      if (!exists) {
        firstAvailableDay = i;
        break;
      }
    }
    setHoursData({
      dia_semana: firstAvailableDay,
      hora_inicio: "08:00",
      hora_fim: "18:00",
    });
    setShowHoursDialog(true);
  };

  const handleEditHours = (hours: BusinessHours) => {
    setEditingHours(hours);
    setHoursData({
      dia_semana: hours.dia_semana,
      hora_inicio: hours.hora_inicio,
      hora_fim: hours.hora_fim,
    });
    setShowHoursDialog(true);
  };

  const handleSaveHours = () => {
    if (editingHours) {
      updateHoursMutation.mutate({
        id: editingHours.id,
        updates: hoursData,
      });
    } else {
      const dayExists = businessHours.some(
        (h: BusinessHours) => h.dia_semana === hoursData.dia_semana,
      );
      if (dayExists) {
        toast.error("Horário para este dia já existe");
        return;
      }
      createHoursMutation.mutate(hoursData);
    }
  };

  const handleAddFeriado = () => {
    setEditingFeriado(null);
    setFeriadoData({
      data: new Date().toISOString().split("T")[0],
      nome: "",
      descricao: "",
    });
    setShowHolidayDialog(true);
  };

  const handleEditFeriado = (feriado: Feriado) => {
    setEditingFeriado(feriado);
    setFeriadoData({
      data: feriado.data,
      nome: feriado.nome,
      descricao: feriado.descricao || "",
    });
    setShowHolidayDialog(true);
  };

  const handleSaveFeriado = () => {
    if (!feriadoData.nome) {
      toast.error("Preencha o nome do feriado");
      return;
    }

    if (editingFeriado) {
      updateFeriadoMutation.mutate({
        id: editingFeriado.id,
        updates: {
          nome: feriadoData.nome,
          descricao: feriadoData.descricao,
        },
      });
    } else {
      const dateExists = feriados.some(
        (f: Feriado) => f.data === feriadoData.data,
      );
      if (dateExists) {
        toast.error("Feriado nesta data já existe");
        return;
      }
      createFeriadoMutation.mutate(feriadoData);
    }
  };

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="text-lg font-semibold">Níveis de SLA e Prioridades</h2>
          <div className="flex gap-2 flex-wrap">
            <div className="flex gap-1 bg-muted rounded-lg p-1">
              <Button
                type="button"
                variant={configViewMode === "grid" ? "default" : "ghost"}
                onClick={() => setConfigViewMode("grid")}
                size="sm"
                className="h-8 px-3"
              >
                <Grid3x3 className="h-4 w-4" />
                Grade
              </Button>
              <Button
                type="button"
                variant={configViewMode === "list" ? "default" : "ghost"}
                onClick={() => setConfigViewMode("list")}
                size="sm"
                className="h-8 px-3"
              >
                <List className="h-4 w-4" />
                Lista
              </Button>
            </div>
            <Button
              onClick={() => sincronizarProblemasMutation.mutate()}
              disabled={sincronizarProblemasMutation.isPending}
              variant="outline"
              size="sm"
              className="gap-2 h-8"
            >
              <RefreshCw className="w-4 h-4" />
              Sincronizar
            </Button>
            <Button
              onClick={() => zerarCacheMutation.mutate()}
              disabled={zerarCacheMutation.isPending}
              variant="destructive"
              size="sm"
              className="gap-2 h-8"
            >
              <RefreshCw className="w-4 h-4" />
              Zerar SLA
            </Button>
            <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
              <DialogTrigger asChild>
                <Button
                  onClick={handleAddConfig}
                  size="sm"
                  className="gap-2 h-8"
                >
                  <Plus className="w-4 h-4" />
                  Adicionar SLA
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>
                    {editingConfig ? "Editar SLA" : "Criar novo SLA"}
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Prioridade</Label>
                    <Input
                      disabled={!!editingConfig}
                      placeholder="Ex: Crítico, Alto, Normal, Baixo"
                      value={formData.prioridade}
                      onChange={(e) =>
                        setFormData({ ...formData, prioridade: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <Label>Tempo de Resposta (horas)</Label>
                    <Input
                      type="number"
                      min="0.5"
                      step="0.5"
                      value={formData.tempo_resposta_horas}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          tempo_resposta_horas: parseFloat(e.target.value),
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>Tempo de Resolução (horas)</Label>
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={formData.tempo_resolucao_horas}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          tempo_resolucao_horas: parseFloat(e.target.value),
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>Descrição</Label>
                    <Input
                      placeholder="Descrição do nível de SLA"
                      value={formData.descricao}
                      onChange={(e) =>
                        setFormData({ ...formData, descricao: e.target.value })
                      }
                    />
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      onClick={() => setShowConfigDialog(false)}
                    >
                      Cancelar
                    </Button>
                    <Button onClick={handleSaveConfig}>
                      {editingConfig ? "Atualizar" : "Criar"}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {configsLoading ? (
          <div className="text-muted-foreground">Carregando...</div>
        ) : configs.length > 0 ? (
          <div>
            {configViewMode === "grid" && (
              <div className="grid gap-3 sm:gap-4 md:grid-cols-2 lg:grid-cols-3">
                {configs.map((config: SLAConfig) => (
                  <SLAConfigCard
                    key={config.id}
                    config={config}
                    onEdit={handleEditConfig}
                    onDelete={() => deleteConfigMutation.mutate(config.id)}
                  />
                ))}
              </div>
            )}
            {configViewMode === "list" && (
              <div className="space-y-3">
                {configs.map((config: SLAConfig) => (
                  <div
                    key={config.id}
                    className="rounded-lg border border-border/60 bg-card overflow-hidden hover:shadow-md hover:border-primary/20 transition-all"
                  >
                    <div className="p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold text-sm">
                            {config.prioridade}
                          </h3>
                          {config.descricao && (
                            <p className="text-sm text-muted-foreground mt-1">
                              {config.descricao}
                            </p>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-4 sm:text-right">
                          <div>
                            <div className="text-xs font-medium text-muted-foreground mb-1">
                              Resposta
                            </div>
                            <div className="font-semibold">
                              {config.tempo_resposta_horas}h
                            </div>
                          </div>
                          <div>
                            <div className="text-xs font-medium text-muted-foreground mb-1">
                              Resolução
                            </div>
                            <div className="font-semibold">
                              {config.tempo_resolucao_horas}h
                            </div>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2 mt-4 pt-4 border-t border-border/40">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleEditConfig(config)}
                          className="flex-1 h-8 text-xs"
                        >
                          <Edit2 className="w-3.5 h-3.5 mr-1" />
                          Editar
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => deleteConfigMutation.mutate(config.id)}
                          className="flex-1 h-8 text-xs"
                        >
                          <Trash2 className="w-3.5 h-3.5 mr-1" />
                          Remover
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            Nenhuma configuração de SLA criada
          </div>
        )}
      </div>

      <div className="border-t pt-8 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="text-lg font-semibold">Horários Comerciais</h2>
          <Dialog open={showHoursDialog} onOpenChange={setShowHoursDialog}>
            <DialogTrigger asChild>
              <Button onClick={handleAddHours} size="sm" className="gap-2 h-8">
                <Plus className="w-4 h-4" />
                Adicionar Horário
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>
                  {editingHours
                    ? "Editar Horário"
                    : "Adicionar Horário Comercial"}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label>Dia da Semana</Label>
                  <Select
                    value={String(hoursData.dia_semana)}
                    onValueChange={(value) =>
                      setHoursData({
                        ...hoursData,
                        dia_semana: parseInt(value),
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DIAS_SEMANA.map((dia) => (
                        <SelectItem key={dia.id} value={String(dia.id)}>
                          {dia.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Início</Label>
                    <Input
                      type="time"
                      value={hoursData.hora_inicio}
                      onChange={(e) =>
                        setHoursData({
                          ...hoursData,
                          hora_inicio: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>Fim</Label>
                    <Input
                      type="time"
                      value={hoursData.hora_fim}
                      onChange={(e) =>
                        setHoursData({
                          ...hoursData,
                          hora_fim: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    onClick={() => setShowHoursDialog(false)}
                  >
                    Cancelar
                  </Button>
                  <Button onClick={handleSaveHours}>
                    {editingHours ? "Atualizar" : "Adicionar"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {hoursLoading ? (
          <div className="text-muted-foreground">Carregando...</div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {DIAS_SEMANA.map((dia) => {
                const horasDia = businessHours.find(
                  (h: BusinessHours) => h.dia_semana === dia.id,
                );
                return (
                  <button
                    key={dia.id}
                    onClick={() => {
                      if (horasDia) {
                        handleEditHours(horasDia);
                      } else {
                        setEditingHours(null);
                        setHoursData({
                          dia_semana: dia.id,
                          hora_inicio: "08:00",
                          hora_fim: "18:00",
                        });
                        setShowHoursDialog(true);
                      }
                    }}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      horasDia
                        ? "border-primary/30 bg-primary/5 hover:border-primary/50 hover:bg-primary/10"
                        : "border-border/40 bg-muted/30 hover:border-border/60 hover:bg-muted/50"
                    }`}
                  >
                    <div className="text-left">
                      <div className="text-xs font-medium text-muted-foreground mb-2">
                        {dia.label}
                      </div>
                      {horasDia ? (
                        <div className="text-sm font-semibold text-primary">
                          {horasDia.hora_inicio} - {horasDia.hora_fim}
                        </div>
                      ) : (
                        <div className="text-xs text-muted-foreground italic">
                          Clique para adicionar
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="rounded-lg border border-border/60 bg-card overflow-hidden">
              <div className="divide-y divide-border/60">
                {DIAS_SEMANA.map((dia) => {
                  const horasDia = businessHours.find(
                    (h: BusinessHours) => h.dia_semana === dia.id,
                  );
                  return (
                    <div
                      key={dia.id}
                      className="p-4 hover:bg-muted/30 transition-colors flex items-center justify-between"
                    >
                      <div className="flex items-center gap-3">
                        <Clock className="w-4 h-4 text-primary flex-shrink-0" />
                        <h3 className="font-medium text-sm">{dia.label}</h3>
                      </div>
                      {horasDia ? (
                        <div className="flex items-center gap-4">
                          <span className="font-semibold text-sm text-primary">
                            {horasDia.hora_inicio} - {horasDia.hora_fim}
                          </span>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleEditHours(horasDia)}
                              className="h-8 px-3"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() =>
                                deleteHoursMutation.mutate(horasDia.id)
                              }
                              className="h-8 px-3"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">
                          Sem horário
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="border-t pt-8 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="text-lg font-semibold">Feriados</h2>
          <Dialog open={showHolidayDialog} onOpenChange={setShowHolidayDialog}>
            <DialogTrigger asChild>
              <Button
                onClick={handleAddFeriado}
                size="sm"
                className="gap-2 h-8"
              >
                <Plus className="w-4 h-4" />
                Adicionar Feriado
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>
                  {editingFeriado ? "Editar Feriado" : "Adicionar Feriado"}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label>Data</Label>
                  <Input
                    type="date"
                    value={feriadoData.data}
                    onChange={(e) =>
                      setFeriadoData({
                        ...feriadoData,
                        data: e.target.value,
                      })
                    }
                    disabled={!!editingFeriado}
                  />
                </div>
                <div>
                  <Label>Nome</Label>
                  <Input
                    placeholder="Ex: Natal, Ano Novo"
                    value={feriadoData.nome}
                    onChange={(e) =>
                      setFeriadoData({
                        ...feriadoData,
                        nome: e.target.value,
                      })
                    }
                  />
                </div>
                <div>
                  <Label>Descrição</Label>
                  <Input
                    placeholder="Descrição do feriado (opcional)"
                    value={feriadoData.descricao}
                    onChange={(e) =>
                      setFeriadoData({
                        ...feriadoData,
                        descricao: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    onClick={() => setShowHolidayDialog(false)}
                  >
                    Cancelar
                  </Button>
                  <Button onClick={handleSaveFeriado}>
                    {editingFeriado ? "Atualizar" : "Adicionar"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {feriadosLoading ? (
          <div className="text-muted-foreground">Carregando...</div>
        ) : feriados.length > 0 ? (
          <div className="rounded-lg border border-border/60 bg-card overflow-hidden">
            <div className="divide-y divide-border/60">
              {feriados
                .sort((a: Feriado, b: Feriado) => a.data.localeCompare(b.data))
                .map((feriado: Feriado) => (
                  <div
                    key={feriado.id}
                    className="p-4 hover:bg-muted/30 transition-colors flex items-center justify-between"
                  >
                    <div className="flex items-start gap-3 flex-1">
                      <Calendar className="w-4 h-4 text-primary flex-shrink-0 mt-1" />
                      <div className="flex-1">
                        <h3 className="font-medium text-sm">{feriado.nome}</h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-muted-foreground">
                            {new Date(
                              feriado.data + "T00:00:00",
                            ).toLocaleDateString("pt-BR")}
                          </span>
                          {feriado.descricao && (
                            <span className="text-xs text-muted-foreground">
                              • {feriado.descricao}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleEditFeriado(feriado)}
                        className="h-8 px-3"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => deleteFeriadoMutation.mutate(feriado.id)}
                        className="h-8 px-3"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            Nenhum feriado configurado
          </div>
        )}
      </div>
    </div>
  );
}
