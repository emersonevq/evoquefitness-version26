import Layout from "@/components/layout/Layout";
import { sectors } from "@/data/sectors";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuthContext } from "@/lib/auth-context";
import { Separator } from "@/components/ui/separator";
import {
  CheckCircle2,
  Copy,
  Ticket,
  Calendar,
  AlertCircle,
  FileText,
  Plus,
  Eye,
  Clock,
  Shield,
  CheckCircle,
  User,
  MapPin,
  AlertTriangle,
  Loader2,
} from "lucide-react";
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
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { FileUploadArea } from "@/components/file-upload/FileUploadArea";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const sector = sectors.find((s) => s.slug === "ti")!;

interface Ticket {
  id: string;
  codigo: string;
  protocolo: string;
  data: string;
  problema: string;
  status: string;
  descricao?: string;
  solicitante?: string;
  cargo?: string;
  email?: string;
  telefone?: string;
  unidade?: string;
  prioridade?: string;
  internet_item?: string;
  data_abertura?: string;
}

export default function TiPage() {
  const { user } = useAuthContext();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [lastCreated, setLastCreated] = useState<{
    codigo: string;
    protocolo: string;
  } | null>(null);
  const [open, setOpen] = useState(false);
  const [successOpen, setSuccessOpen] = useState(false);
  const [copied, setCopied] = useState<"codigo" | "protocolo" | "all" | null>(
    null
  );
  const [unidades, setUnidades] = useState<
    { id: number; nome: string; cidade: string }[]
  >([]);
  const [problemas, setProblemas] = useState<
    {
      id: number;
      nome: string;
      prioridade: string;
      requer_internet: boolean;
      tempo_resolucao_horas?: number | null;
    }[]
  >([]);

  // 🔥 CARREGAR CHAMADOS DO USUÁRIO
  useEffect(() => {
    const fetchTickets = async () => {
      if (!user) return;

      try {
        setLoading(true);
        const response = await apiFetch("/chamados");
        if (!response.ok) {
          throw new Error("Erro ao carregar chamados");
        }

        const data = await response.json();

        // Filtrar apenas chamados do usuário logado (se necessário)
        // Se a API já retorna apenas os chamados do usuário, remova o filtro
        const userTickets = Array.isArray(data)
          ? data.filter(
              (ticket: any) =>
                ticket.email === user.email ||
                ticket.solicitante === user.name
            )
          : [];

        // Mapear para o formato esperado
        const mappedTickets: Ticket[] = userTickets.map((ticket: any) => ({
          id: String(ticket.id),
          codigo: ticket.codigo,
          protocolo: ticket.protocolo,
          data: ticket.data_abertura?.slice(0, 10) || ticket.data_abertura,
          problema:
            ticket.problema === "Internet" && ticket.internet_item
              ? `Internet - ${ticket.internet_item}`
              : ticket.problema,
          status: ticket.status,
          descricao: ticket.descricao,
          solicitante: ticket.solicitante,
          cargo: ticket.cargo,
          email: ticket.email,
          telefone: ticket.telefone,
          unidade: ticket.unidade,
          prioridade: ticket.prioridade,
          internet_item: ticket.internet_item,
          data_abertura: ticket.data_abertura,
        }));

        setTickets(mappedTickets);
      } catch (error) {
        console.error("Erro ao carregar chamados:", error);
        // Opcional: mostrar toast de erro
      } finally {
        setLoading(false);
      }
    };

    fetchTickets();
  }, [user]); // Recarrega quando o usuário muda

  // Carregar unidades e problemas quando abre o modal
  useEffect(() => {
    if (!open) return;

    apiFetch("/unidades")
      .then((r) => {
        if (!r.ok) return Promise.reject(new Error("fail"));
        return r.json();
      })
      .then((data) => {
        if (Array.isArray(data)) setUnidades(data);
        else setUnidades([]);
      })
      .catch((err) => {
        console.error("Error loading unidades:", err);
        setUnidades([]);
      });

    apiFetch("/problemas")
      .then((r) => {
        if (!r.ok) {
          console.error("Failed to load problemas:", r.status, r.statusText);
          return Promise.reject(new Error("fail"));
        }
        return r.json();
      })
      .then((data) => {
        if (Array.isArray(data)) setProblemas(data);
        else {
          console.error("Invalid problemas data format:", data);
          setProblemas([]);
        }
      })
      .catch((err) => {
        console.error("Error loading problemas:", err);
        setProblemas([]);
      });
  }, [open]);

  const handleCopy = async (
    text: string,
    type: "codigo" | "protocolo" | "all"
  ) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(type);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      Aberto:
        "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20",
      "Em Andamento":
        "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20",
      Resolvido:
        "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20",
      Fechado:
        "bg-gray-500/10 text-gray-700 dark:text-gray-400 border-gray-500/20",
    };
    return colors[status] || colors.Aberto;
  };

  const getPrioridadeColor = (prioridade: string) => {
    const colors: Record<string, string> = {
      Crítica:
        "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20",
      Alta: "bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/20",
      Normal:
        "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20",
      Baixa:
        "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20",
    };
    return colors[prioridade] || colors.Normal;
  };

  const handleViewDetails = (ticket: Ticket) => {
    setSelectedTicket(ticket);
    setDetailsOpen(true);
  };

  return (
    <Layout>
      {/* Hero Section */}
      <section className="w-full bg-gradient-to-br from-primary via-primary/95 to-primary/90 relative overflow-hidden">
        <div className="absolute inset-0 bg-grid-white/[0.05] bg-[size:20px_20px]" />
        <div className="absolute inset-0 bg-gradient-to-t from-background/10 to-transparent" />

        <div className="container relative py-16 sm:py-20">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full mb-6">
              <Shield className="w-4 h-4 text-white" />
              <span className="text-sm font-medium text-white">
                Suporte Técnico 24/7
              </span>
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white drop-shadow-lg mb-4">
              {sector.title}
            </h1>
            <p className="text-lg sm:text-xl text-white/90 max-w-2xl leading-relaxed">
              {sector.description}
            </p>

            <div className="flex flex-wrap gap-3 mt-8">
              {user?.nivel_acesso === "Administrador" && (
                <Button
                  asChild
                  size="lg"
                  variant="secondary"
                  className="rounded-full shadow-lg hover:shadow-xl transition-all"
                >
                  <Link to="/setor/ti/admin">
                    <Shield className="w-4 h-4 mr-2" />
                    Painel Administrativo
                  </Link>
                </Button>
              )}

              <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                  <Button
                    size="lg"
                    className="rounded-full bg-white text-primary hover:bg-white/90 shadow-lg hover:shadow-xl transition-all"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Abrir Novo Chamado
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="text-2xl flex items-center gap-2">
                      <Ticket className="w-6 h-6 text-primary" />
                      Abrir Chamado de TI
                    </DialogTitle>
                  </DialogHeader>
                  <TicketForm
                    problemas={problemas}
                    unidades={unidades}
                    onSubmit={async (payload) => {
                      try {
                        const fd = new FormData();
                        fd.set("solicitante", payload.nome);
                        fd.set("cargo", payload.cargo);
                        fd.set("email", payload.email);
                        fd.set("telefone", payload.telefone);
                        fd.set("unidade", payload.unidade);
                        fd.set("problema", payload.problema);
                        if (payload.internetItem)
                          fd.set("internetItem", payload.internetItem);
                        if (payload.descricao)
                          fd.set("descricao", payload.descricao);
                        if (payload.files && payload.files.length > 0) {
                          for (const f of payload.files) fd.append("files", f);
                        }
                        const res = await apiFetch(
                          "/chamados/with-attachments",
                          {
                            method: "POST",
                            body: fd,
                          }
                        );
                        if (!res.ok) throw new Error("Falha ao criar chamado");
                        const created = await res.json();

                        const problemaFmt =
                          created.problema === "Internet" &&
                          created.internet_item
                            ? `Internet - ${created.internet_item}`
                            : created.problema;

                        const problemaInfo = problemas.find(
                          (p) => p.nome === created.problema
                        );

                        const newTicket: Ticket = {
                          id: String(created.id),
                          codigo: created.codigo,
                          protocolo: created.protocolo,
                          data:
                            created.data_abertura?.slice(0, 10) ||
                            new Date().toISOString().slice(0, 10),
                          problema: problemaFmt,
                          status: created.status,
                          solicitante: created.solicitante,
                          cargo: created.cargo,
                          email: created.email,
                          telefone: created.telefone,
                          unidade: created.unidade,
                          descricao: created.descricao,
                          prioridade: problemaInfo?.prioridade || "Normal",
                          internet_item: created.internet_item || undefined,
                          data_abertura: created.data_abertura,
                        };

                        setTickets((prev) => [newTicket, ...prev]);
                        setLastCreated({
                          codigo: created.codigo,
                          protocolo: created.protocolo,
                        });
                        setOpen(false);
                        setSuccessOpen(true);
                      } catch (e) {
                        console.error(e);
                        alert(
                          "Não foi possível abrir o chamado. Tente novamente."
                        );
                      }
                    }}
                  />
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="container py-8 sm:py-12">
        <div className="max-w-7xl mx-auto">
          {/* Success Alert */}
          {lastCreated && (
            <Card className="mb-6 border-green-500/20 bg-green-500/5">
              <CardContent className="p-6">
                <div className="flex items-start gap-4">
                  <div className="rounded-full bg-green-500/10 p-2">
                    <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-green-900 dark:text-green-100 mb-1">
                      Chamado criado com sucesso!
                    </h3>
                    <p className="text-sm text-green-800 dark:text-green-200 mb-3">
                      Seu chamado foi registrado. Guarde essas informações para
                      acompanhamento.
                    </p>
                    <div className="flex flex-wrap gap-3 text-sm">
                      <div className="flex items-center gap-2 bg-white dark:bg-gray-900 px-3 py-1.5 rounded-lg border border-green-500/20">
                        <span className="text-green-700 dark:text-green-300 font-medium">
                          Código:
                        </span>
                        <span className="font-mono font-semibold text-green-900 dark:text-green-100">
                          {lastCreated.codigo}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 bg-white dark:bg-gray-900 px-3 py-1.5 rounded-lg border border-green-500/20">
                        <span className="text-green-700 dark:text-green-300 font-medium">
                          Protocolo:
                        </span>
                        <span className="font-mono font-semibold text-green-900 dark:text-green-100">
                          {lastCreated.protocolo}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Tickets Table */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-2xl flex items-center gap-2">
                    <FileText className="w-6 h-6 text-primary" />
                    Meus Chamados
                  </CardTitle>
                  <CardDescription className="mt-1">
                    Acompanhe o status de todos os seus chamados abertos
                  </CardDescription>
                </div>
                <Badge variant="secondary" className="hidden sm:flex">
                  {tickets.length}{" "}
                  {tickets.length === 1 ? "chamado" : "chamados"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-primary animate-spin mb-4" />
                  <p className="text-sm text-muted-foreground">
                    Carregando chamados...
                  </p>
                </div>
              ) : (
                <div className="rounded-lg border overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="px-4 py-3 text-left text-sm font-semibold">
                            Código
                          </th>
                          <th className="px-4 py-3 text-left text-sm font-semibold">
                            Protocolo
                          </th>
                          <th className="px-4 py-3 text-right text-sm font-semibold">
                            Ações
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {tickets.length === 0 ? (
                          <tr>
                            <td
                              className="px-4 py-12 text-center text-muted-foreground"
                              colSpan={3}
                            >
                              <div className="flex flex-col items-center gap-3">
                                <div className="rounded-full bg-muted p-4">
                                  <Ticket className="w-8 h-8 text-muted-foreground" />
                                </div>
                                <div>
                                  <p className="font-medium">
                                    Nenhum chamado encontrado
                                  </p>
                                  <p className="text-sm mt-1">
                                    Você ainda não abriu nenhum chamado de
                                    suporte.
                                  </p>
                                </div>
                              </div>
                            </td>
                          </tr>
                        ) : (
                          tickets.map((t) => (
                            <tr
                              key={t.id}
                              className="hover:bg-muted/30 transition-colors"
                            >
                              <td className="px-4 py-4">
                                <div className="flex flex-col gap-1">
                                  <span className="font-mono text-sm font-medium">
                                    {t.codigo}
                                  </span>
                                  <Badge
                                    variant="outline"
                                    className={`${getStatusColor(t.status)} w-fit text-xs`}
                                  >
                                    {t.status}
                                  </Badge>
                                </div>
                              </td>
                              <td className="px-4 py-4">
                                <span className="font-mono text-sm text-muted-foreground">
                                  {t.protocolo}
                                </span>
                              </td>
                              <td className="px-4 py-4 text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="gap-2"
                                  onClick={() => handleViewDetails(t)}
                                >
                                  <Eye className="w-4 h-4" />
                                  <span className="hidden sm:inline">
                                    Ver detalhes
                                  </span>
                                  <span className="sm:hidden">Ver</span>
                                </Button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Modal de Detalhes do Chamado */}
      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          {selectedTicket && (
            <>
              <DialogHeader>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <DialogTitle className="text-2xl flex items-center gap-2 mb-2">
                      <Ticket className="w-6 h-6 text-primary" />
                      Detalhes do Chamado
                    </DialogTitle>
                    <div className="flex flex-wrap gap-2">
                      <Badge
                        variant="outline"
                        className="font-mono text-sm px-3 py-1"
                      >
                        {selectedTicket.codigo}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={getStatusColor(selectedTicket.status)}
                      >
                        {selectedTicket.status}
                      </Badge>
                      {selectedTicket.prioridade && (
                        <Badge
                          variant="outline"
                          className={getPrioridadeColor(
                            selectedTicket.prioridade
                          )}
                        >
                          {selectedTicket.prioridade}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              </DialogHeader>

              <div className="space-y-6 pt-4">
                {/* Informações do Chamado */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2 pb-2 border-b">
                    <div className="rounded-lg bg-primary/10 p-2">
                      <FileText className="w-4 h-4 text-primary" />
                    </div>
                    <h3 className="font-semibold">Informações do Chamado</h3>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        Data de Abertura
                      </Label>
                      <p className="text-sm font-medium">
                        {new Date(selectedTicket.data).toLocaleDateString(
                          "pt-BR",
                          {
                            day: "2-digit",
                            month: "long",
                            year: "numeric",
                          }
                        )}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Protocolo
                      </Label>
                      <p className="text-sm font-mono font-medium">
                        {selectedTicket.protocolo}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Problema Reportado
                      </Label>
                      <p className="text-sm font-medium">
                        {selectedTicket.problema}
                      </p>
                    </div>

                    {selectedTicket.unidade && (
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          Unidade
                        </Label>
                        <p className="text-sm font-medium">
                          {selectedTicket.unidade}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                <Separator />

                {/* Informações do Solicitante */}
                {selectedTicket.solicitante && (
                  <>
                    <div className="space-y-4">
                      <div className="flex items-center gap-2 pb-2 border-b">
                        <div className="rounded-lg bg-primary/10 p-2">
                          <User className="w-4 h-4 text-primary" />
                        </div>
                        <h3 className="font-semibold">Solicitante</h3>
                      </div>

                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">
                            Nome
                          </Label>
                          <p className="text-sm font-medium">
                            {selectedTicket.solicitante}
                          </p>
                        </div>

                        {selectedTicket.cargo && (
                          <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">
                              Cargo
                            </Label>
                            <p className="text-sm font-medium">
                              {selectedTicket.cargo}
                            </p>
                          </div>
                        )}

                        {selectedTicket.email && (
                          <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">
                              E-mail
                            </Label>
                            <p className="text-sm font-medium">
                              {selectedTicket.email}
                            </p>
                          </div>
                        )}

                        {selectedTicket.telefone && (
                          <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">
                              Telefone
                            </Label>
                            <p className="text-sm font-medium">
                              {selectedTicket.telefone}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                    <Separator />
                  </>
                )}

                {/* Descrição */}
                {selectedTicket.descricao && (
                  <div className="space-y-2">
                    <Label className="text-sm font-semibold">
                      Descrição do Problema
                    </Label>
                    <div className="rounded-lg bg-muted/50 p-4">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">
                        {selectedTicket.descricao}
                      </p>
                    </div>
                  </div>
                )}

                {/* Ações */}
                <div className="flex justify-end gap-2 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => setDetailsOpen(false)}
                  >
                    Fechar
                  </Button>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Success Modal */}
      <Dialog open={successOpen} onOpenChange={setSuccessOpen}>
        <DialogContent className="max-w-md p-0 gap-0 overflow-hidden">
          {lastCreated && (
            <div className="w-full">
              <div className="relative bg-gradient-to-br from-green-500 via-emerald-500 to-teal-500 px-6 py-8 text-center overflow-hidden">
                <div className="absolute inset-0 bg-grid-white/[0.1] bg-[size:20px_20px]" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />

                <div className="relative space-y-4">
                  <div className="flex justify-center">
                    <div className="relative">
                      <div className="absolute inset-0 bg-white/20 rounded-full blur-xl animate-pulse" />
                      <div className="relative rounded-full bg-white/10 backdrop-blur-sm p-4 border-2 border-white/20">
                        <CheckCircle2 className="w-12 h-12 text-white" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <h2 className="text-3xl font-extrabold text-white drop-shadow-lg">
                      Chamado Criado!
                    </h2>
                    <p className="text-white/90 text-sm max-w-xs mx-auto">
                      Seu chamado foi registrado com sucesso. Nossa equipe já
                      foi notificada.
                    </p>
                  </div>
                </div>
              </div>

              <div className="p-6 space-y-4">
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                      <Ticket className="w-3.5 h-3.5" />
                      Código do Chamado
                    </Label>
                    <div className="relative group">
                      <div className="bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border-2 border-primary/20 rounded-xl p-4 transition-all hover:border-primary/30 hover:shadow-md">
                        <div className="font-mono font-bold text-xl text-primary tracking-wide">
                          {lastCreated.codigo}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() =>
                          handleCopy(lastCreated.codigo, "codigo")
                        }
                      >
                        {copied === "codigo" ? (
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5" />
                      Número de Protocolo
                    </Label>
                    <div className="relative group">
                      <div className="bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent border-2 border-emerald-500/20 rounded-xl p-4 transition-all hover:border-emerald-500/30 hover:shadow-md">
                        <div className="font-mono font-bold text-xl text-emerald-600 dark:text-emerald-400 tracking-wide">
                          {lastCreated.protocolo}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() =>
                          handleCopy(lastCreated.protocolo, "protocolo")
                        }
                      >
                        {copied === "protocolo" ? (
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-4">
                  <div className="flex gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
                        Importante
                      </p>
                      <p className="text-xs text-amber-800 dark:text-amber-200 leading-relaxed">
                        Guarde essas informações. Você precisará delas para
                        consultar o andamento do seu chamado.
                      </p>
                    </div>
                  </div>
                </div>

                <Separator />

                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() =>
                      handleCopy(
                        `Código: ${lastCreated.codigo}\nProtocolo: ${lastCreated.protocolo}`,
                        "all"
                      )
                    }
                  >
                    {copied === "all" ? (
                      <>
                        <CheckCircle className="w-4 h-4 mr-2 text-green-600" />
                        Copiado!
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4 mr-2" />
                        Copiar Tudo
                      </>
                    )}
                  </Button>
                  <Button
                    className="flex-1"
                    onClick={() => {
                      setSuccessOpen(false);
                      setCopied(null);
                    }}
                  >
                    Concluir
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Layout>
  );
}

function TicketForm(props: {
  problemas?: {
    id: number;
    nome: string;
    prioridade: string;
    requer_internet: boolean;
    tempo_resolucao_horas?: number | null;
  }[];
  unidades?: { id: number; nome: string; cidade: string }[];
  onSubmit: (payload: {
    nome: string;
    cargo: string;
    email: string;
    telefone: string;
    unidade: string;
    problema: string;
    internetItem?: string;
    descricao?: string;
    files?: File[];
  }) => void;
}) {
  const { onSubmit } = props;
  const listaProblemas = Array.isArray(props.problemas) ? props.problemas : [];
  const listaUnidades = Array.isArray(props.unidades) ? props.unidades : [];
  const [form, setForm] = useState({
    nome: "",
    cargo: "",
    email: "",
    telefone: "",
    unidade: "",
    problema: "",
    internetItem: "",
    descricao: "",
  });
  const [files, setFiles] = useState<File[]>([]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();

    const fieldLabels: Record<string, string> = {
      nome: "Nome do solicitante",
      cargo: "Cargo",
      email: "E-mail",
      telefone: "Telefone",
      unidade: "Unidade",
      problema: "Problema Reportado",
      descricao: "Descrição do problema",
    };

    const requiredFields = [
      "nome",
      "cargo",
      "email",
      "telefone",
      "unidade",
      "problema",
      "descricao",
    ] as const;
    const missingFields = requiredFields.filter((field) => !form[field].trim());

    if (missingFields.length > 0) {
      const missingLabels = missingFields
        .map((field) => fieldLabels[field])
        .join(", ");
      alert(
        `Campos obrigatórios não preenchidos: ${missingLabels}\n\nOs arquivos são opcionais.`
      );
      return;
    }

    if (selectedProblem?.requer_internet && !form.internetItem.trim()) {
      alert("Selecione o item de Internet.");
      return;
    }
    onSubmit({ ...form, files });
  };

  const selectedProblem = useMemo(
    () => listaProblemas.find((p) => p.nome === form.problema) || null,
    [listaProblemas, form.problema]
  );

  const formatTempo = (horas: number | null | undefined) => {
    if (!horas) return null;
    if (horas < 24) return `${horas}h`;
    const dias = horas / 24;
    return dias % 1 === 0 ? `${dias}d` : `${horas}h`;
  };

  const getPrioridadeColor = (prioridade: string) => {
    const colors: Record<string, string> = {
      Crítica:
        "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20",
      Alta: "bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/20",
      Normal:
        "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20",
      Baixa:
        "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20",
    };
    return colors[prioridade] || colors.Normal;
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b">
          <div className="rounded-lg bg-primary/10 p-2">
            <AlertCircle className="w-4 h-4 text-primary" />
          </div>
          <h3 className="font-semibold">Informações do Solicitante</h3>
        </div>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="nome">Nome completo *</Label>
            <Input
              id="nome"
              placeholder="Digite seu nome completo"
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              required
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="cargo">Cargo *</Label>
              <Select
                value={form.cargo}
                onValueChange={(v) => setForm({ ...form, cargo: v })}
              >
                <SelectTrigger id="cargo">
                  <SelectValue placeholder="Selecione seu cargo" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Coordenador">Coordenador</SelectItem>
                  <SelectItem value="Funcionário">Funcionário</SelectItem>
                  <SelectItem value="Gerente">Gerente</SelectItem>
                  <SelectItem value="Gerente regional">
                    Gerente regional
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="telefone">Telefone *</Label>
              <Input
                id="telefone"
                inputMode="numeric"
                pattern="[0-9]*"
                placeholder="11987654321"
                value={form.telefone}
                onChange={(e) => setForm({ ...form, telefone: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="email">E-mail *</Label>
            <Input
              id="email"
              type="email"
              placeholder="seu.email@empresa.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </div>
        </div>
      </div>

      <Separator />

      <div className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b">
          <div className="rounded-lg bg-primary/10 p-2">
            <Ticket className="w-4 h-4 text-primary" />
          </div>
          <h3 className="font-semibold">Detalhes do Chamado</h3>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="grid gap-2">
            <Label>Unidade *</Label>
            <Select
              value={form.unidade}
              onValueChange={(v) => setForm({ ...form, unidade: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione a unidade" />
              </SelectTrigger>
              <SelectContent>
                {listaUnidades.map((u) => (
                  <SelectItem key={u.id} value={u.nome}>
                    {new RegExp(`(\\s*-\\s*${u.id})\\s*$`).test(u.nome)
                      ? u.nome
                      : `${u.nome} - ${u.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label>Tipo de Problema *</Label>
            <Select
              value={form.problema}
              onValueChange={(v) =>
                setForm({ ...form, problema: v, internetItem: "" })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione o problema" />
              </SelectTrigger>
              <SelectContent>
                {listaProblemas.map((p) => (
                  <SelectItem key={p.id} value={p.nome}>
                    {p.nome}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {selectedProblem && (
          <Card className="border-2">
            <CardContent className="p-4">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Prioridade:</span>
                  <Badge
                    variant="outline"
                    className={getPrioridadeColor(selectedProblem.prioridade)}
                  >
                    {selectedProblem.prioridade}
                  </Badge>
                </div>
                {selectedProblem.tempo_resolucao_horas && (
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Prazo SLA:</span>
                    <Badge variant="outline">
                      {formatTempo(selectedProblem.tempo_resolucao_horas)}
                    </Badge>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {selectedProblem?.requer_internet && (
          <div className="grid gap-2">
            <Label>Item de Internet *</Label>
            <Select
              value={form.internetItem}
              onValueChange={(v) => setForm({ ...form, internetItem: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione o item específico" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Antenas">Antenas</SelectItem>
                <SelectItem value="Cabo de rede">Cabo de rede</SelectItem>
                <SelectItem value="DVR">DVR</SelectItem>
                <SelectItem value="Roteador/Modem">Roteador/Modem</SelectItem>
                <SelectItem value="Switch">Switch</SelectItem>
                <SelectItem value="Wi-fi">Wi-fi</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="grid gap-2">
          <Label htmlFor="descricao">Descrição detalhada *</Label>
          <textarea
            id="descricao"
            className="min-h-[120px] rounded-lg border border-input bg-background p-4 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            placeholder="Descreva o problema com o máximo de detalhes possível. Inclua: o que aconteceu, quando começou, se há mensagens de erro, etc."
            value={form.descricao}
            onChange={(e) => setForm({ ...form, descricao: e.target.value })}
            required
          />
        </div>

        <div className="grid gap-2">
          <Label>Anexar Arquivos (opcional)</Label>
          <FileUploadArea files={files} onChange={setFiles} maxSize={25} />
          <p className="text-xs text-muted-foreground">
            Aceita imagens, documentos e vídeos até 25MB
          </p>
        </div>
      </div>

      <Separator />

      <div className="flex items-center justify-end gap-3 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => window.history.back()}
        >
          Cancelar
        </Button>
        <Button type="submit" className="min-w-[120px]">
          Abrir Chamado
        </Button>
      </div>
    </form>
  );
}
