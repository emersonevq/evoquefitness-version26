import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertCircle, CheckCircle2, RefreshCw, Loader, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface SyncStats {
  total_chamados?: number;
  total_recalculados?: number;
  sincronizados?: number;
  atualizados?: number;
  em_dia?: number;
  vencidos?: number;
  em_andamento?: number;
  congelados?: number;
  erros?: number;
}

interface PopulateStats {
  ok?: boolean;
  message?: string;
  total_atualizados?: number;
  total_pulados?: number;
  erros?: number;
  cache_invalidado?: boolean;
}

export function SLASync() {
  const [loading, setLoading] = useState(false);
  const [populatingFirstResponse, setPopulatingFirstResponse] = useState(false);
  const [stats, setStats] = useState<SyncStats | null>(null);
  const [populateStats, setPopulateStats] = useState<PopulateStats | null>(null);

  const handleSyncAll = async () => {
    setLoading(true);
    try {
      const response = await api.post("/sla/sync/todos-chamados");
      setStats(response.data);
      toast.success("Sincronização concluída com sucesso!");
    } catch (error: any) {
      toast.error(
        error.response?.data?.detail || "Erro ao sincronizar chamados",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRecalculate = async () => {
    setLoading(true);
    try {
      const response = await api.post("/sla/recalcular/painel");
      setStats(response.data);
      toast.success("Recálculo de SLAs concluído com sucesso!");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Erro ao recalcular SLAs");
    } finally {
      setLoading(false);
    }
  };

  const handlePopulateFirstResponse = async () => {
    setPopulatingFirstResponse(true);
    try {
      const response = await api.post("/sla/maintenance/populate-primeira-resposta");
      setPopulateStats(response.data);
      toast.success(
        `✓ ${response.data.total_atualizados} chamados atualizados com sucesso!`,
      );
    } catch (error: any) {
      toast.error(
        error.response?.data?.detail ||
          "Erro ao popular data de primeira resposta",
      );
    } finally {
      setPopulatingFirstResponse(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800 p-4">
        <div className="flex gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800 dark:text-amber-200">
            <p className="font-semibold mb-1">Importante</p>
            <p>
              Use as opções abaixo para sincronizar chamados existentes com a
              tabela de SLA. A sincronização inicial deve ser feita uma única
              vez após a criação das configurações de SLA.
            </p>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Sincronização Inicial */}
        <Card className="p-6 space-y-4">
          <div className="space-y-2">
            <h3 className="font-semibold text-lg">Sincronização Inicial</h3>
            <p className="text-sm text-muted-foreground">
              Sincroniza todos os chamados existentes com a tabela de histórico
              de SLA. Execute isso uma única vez após criar as configurações de
              SLA.
            </p>
          </div>

          <div className="bg-muted/50 rounded-lg p-3 text-sm space-y-2">
            <p className="font-medium">O que acontece:</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>Verifica cada chamado existente</li>
              <li>Cria histórico inicial de SLA</li>
              <li>Calcula métricas de tempo decorrido</li>
              <li>Avalia status SLA (ok/vencido)</li>
            </ul>
          </div>

          <Button
            onClick={handleSyncAll}
            disabled={loading}
            className="w-full gap-2"
            variant="default"
          >
            {loading ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Sincronizando...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Sincronizar Todos os Chamados
              </>
            )}
          </Button>
        </Card>

        {/* Recálculo de SLAs */}
        <Card className="p-6 space-y-4">
          <div className="space-y-2">
            <h3 className="font-semibold text-lg">Recálculo de SLAs</h3>
            <p className="text-sm text-muted-foreground">
              Recalcula todos os SLAs com base no estado atual dos chamados. Use
              isto para atualizar métricas após mudanças nas configurações de
              SLA.
            </p>
          </div>

          <div className="bg-muted/50 rounded-lg p-3 text-sm space-y-2">
            <p className="font-medium">O que acontece:</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>Recalcula tempo decorrido para cada chamado</li>
              <li>Atualiza status SLA (ok/vencido/etc)</li>
              <li>Refaz comparações com limites atualizados</li>
              <li>Registra novos dados de auditoria</li>
            </ul>
          </div>

          <Button
            onClick={handleRecalculate}
            disabled={loading}
            className="w-full gap-2"
            variant="secondary"
          >
            {loading ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Recalculando...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Recalcular SLAs
              </>
            )}
          </Button>
        </Card>

        {/* Manutenção: Popular Data de Primeira Resposta */}
        <Card className="p-6 space-y-4 border-blue-200 dark:border-blue-800">
          <div className="space-y-2">
            <h3 className="font-semibold text-lg flex items-center gap-2">
              <Wrench className="w-4 h-4" />
              Manutenção de Dados
            </h3>
            <p className="text-sm text-muted-foreground">
              Preenche o campo de primeira resposta em chamados antigos usando o
              histórico. Útil para corrigir dados faltantes após migração.
            </p>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 text-sm space-y-2">
            <p className="font-medium text-blue-900 dark:text-blue-400">
              O que acontece:
            </p>
            <ul className="list-disc list-inside space-y-1 text-blue-800 dark:text-blue-300">
              <li>Busca primeira mudança de status em cada chamado</li>
              <li>Preenche data_primeira_resposta automaticamente</li>
              <li>Invalida cache para recálculo de métricas</li>
              <li>Corrige tempos médios de resposta</li>
            </ul>
          </div>

          <Button
            onClick={handlePopulateFirstResponse}
            disabled={populatingFirstResponse}
            className="w-full gap-2"
            variant="outline"
          >
            {populatingFirstResponse ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Processando...
              </>
            ) : (
              <>
                <Wrench className="w-4 h-4" />
                Popular Data de Resposta
              </>
            )}
          </Button>
        </Card>
      </div>

      {/* Resultados da Manutenção */}
      {populateStats && (
        <Card className="p-6 border-blue-200 dark:border-blue-800">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-blue-600" />
            Resultados da Manutenção
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Atualizados</p>
              <p className="text-2xl font-bold text-green-600">
                {populateStats.total_atualizados}
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Pulados</p>
              <p className="text-2xl font-bold text-amber-600">
                {populateStats.total_pulados}
              </p>
            </div>

            {populateStats.erros > 0 && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Erros</p>
                <p className="text-2xl font-bold text-red-600">
                  {populateStats.erros}
                </p>
              </div>
            )}

            {populateStats.cache_invalidado && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Status</p>
                <p className="text-sm font-semibold text-blue-600">
                  Cache Limpo ✓
                </p>
              </div>
            )}
          </div>

          {populateStats.message && (
            <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm text-blue-800 dark:text-blue-300">
              {populateStats.message}
            </div>
          )}
        </Card>
      )}

      {/* Resultados */}
      {stats && (
        <Card className="p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-600" />
            Resultados da Operação
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {stats.total_chamados && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">
                  Total de Chamados
                </p>
                <p className="text-2xl font-bold">{stats.total_chamados}</p>
              </div>
            )}

            {stats.sincronizados !== undefined && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Sincronizados</p>
                <p className="text-2xl font-bold text-green-600">
                  {stats.sincronizados}
                </p>
              </div>
            )}

            {stats.atualizados !== undefined && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Atualizados</p>
                <p className="text-2xl font-bold text-blue-600">
                  {stats.atualizados}
                </p>
              </div>
            )}

            {stats.total_recalculados !== undefined && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Recalculados</p>
                <p className="text-2xl font-bold text-blue-600">
                  {stats.total_recalculados}
                </p>
              </div>
            )}

            {stats.em_dia !== undefined && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Em Dia</p>
                <p className="text-2xl font-bold text-green-600">
                  {stats.em_dia}
                </p>
              </div>
            )}

            {stats.vencidos !== undefined && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Vencidos</p>
                <p className="text-2xl font-bold text-red-600">
                  {stats.vencidos}
                </p>
              </div>
            )}

            {stats.em_andamento !== undefined && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Em Andamento</p>
                <p className="text-2xl font-bold text-amber-600">
                  {stats.em_andamento}
                </p>
              </div>
            )}

            {stats.congelados !== undefined && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Congelados</p>
                <p className="text-2xl font-bold text-blue-600">
                  {stats.congelados}
                </p>
              </div>
            )}

            {stats.erros !== undefined && stats.erros > 0 && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Erros</p>
                <p className="text-2xl font-bold text-red-600">{stats.erros}</p>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
