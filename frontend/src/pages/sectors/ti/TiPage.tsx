import Layout from "@/components/layout/Layout";
import { sectors } from "@/data/sectors";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuthContext } from "@/lib/auth-context";
import { Separator } from "@/components/ui/separator";
import { CheckCircle, Copy } from "lucide-react";
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

const sector = sectors.find((s) => s.slug === "ti")!;

interface Ticket {
  id: string;
  codigo: string;
  protocolo: string;
  data: string;
  problema: string;
  status: string;
}

export default function TiPage() {
  const API_BASE: string = (import.meta as any)?.env?.VITE_API_BASE || "/api";
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [lastCreated, setLastCreated] = useState<{
    codigo: string;
    protocolo: string;
  } | null>(null);
  const [open, setOpen] = useState(false);
  const [successOpen, setSuccessOpen] = useState(false);
  const [unidades, setUnidades] = useState<
    { id: number; nome: string; cidade: string }[]
  >([]);
  const [problemas, setProblemas] = useState<
    { id: number; nome: string; prioridade: string; requer_internet: boolean }[]
  >([]);

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

  return (
    <Layout>
      <section className="w-full">
        <div className="brand-gradient">
          <div className="container py-10 sm:py-14">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-primary-foreground drop-shadow">
              {sector.title}
            </h1>
            <p className="mt-2 text-primary-foreground/90 max-w-2xl">
              {sector.description}
            </p>
          </div>
        </div>
      </section>

      <section className="container py-8">
        {lastCreated && (
          <div className="mb-4 rounded-lg border border-border/60 bg-card p-4 text-sm">
            <div className="font-semibold mb-1">Chamado criado com sucesso</div>
            <div>
              Código <span className="font-semibold">{lastCreated.codigo}</span>{" "}
              e Protocolo{" "}
              <span className="font-semibold">{lastCreated.protocolo}</span>{" "}
              gerados e salvos.
            </div>
            <div className="text-muted-foreground mt-1">
              Guarde essas informações para futuras consultas.
            </div>
          </div>
        )}
        <div className="flex items-center justify-between gap-4">
          {/** show admin shortcut only to Administrador */}
          {(() => {
            const { user } = useAuthContext();
            return user?.nivel_acesso === "Administrador" ? (
              <div className="md:hidden">
                <Button asChild variant="secondary" className="rounded-full">
                  <Link to="/setor/ti/admin">Painel administrativo</Link>
                </Button>
              </div>
            ) : null;
          })()}
          <h2 className="text-lg sm:text-xl font-semibold">
            Histórico de chamados
          </h2>
          {(() => {
            const { user } = useAuthContext();
            return user?.nivel_acesso === "Administrador" ? (
              <div className="hidden md:block">
                <Button asChild className="mr-2 rounded-full">
                  <Link to="/setor/ti/admin">Painel administrativo</Link>
                </Button>
              </div>
            ) : null;
          })()}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="rounded-full">Abrir novo chamado</Button>
            </DialogTrigger>
            <DialogContent className="max-w-xl">
              <DialogHeader>
                <DialogTitle>Abrir chamado</DialogTitle>
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
                    const res = await apiFetch("/chamados/with-attachments", {
                      method: "POST",
                      body: fd,
                    });
                    if (!res.ok) throw new Error("Falha ao criar chamado");
                    const created: {
                      id: number;
                      codigo: string;
                      protocolo: string;
                      data_abertura: string;
                      problema: string;
                      internet_item?: string | null;
                      status: string;
                    } = await res.json();

                    const problemaFmt =
                      created.problema === "Internet" && created.internet_item
                        ? `Internet - ${created.internet_item}`
                        : created.problema;

                    setTickets((prev) => [
                      {
                        id: String(created.id),
                        codigo: created.codigo,
                        protocolo: created.protocolo,
                        data:
                          created.data_abertura?.slice(0, 10) ||
                          new Date().toISOString().slice(0, 10),
                        problema: problemaFmt,
                        status: created.status,
                      },
                      ...prev,
                    ]);
                    setLastCreated({
                      codigo: created.codigo,
                      protocolo: created.protocolo,
                    });
                    setOpen(false);
                    setSuccessOpen(true);
                  } catch (e) {
                    console.error(e);
                    alert("Não foi possível abrir o chamado. Tente novamente.");
                  }
                }}
              />
            </DialogContent>
          </Dialog>
        </div>

        <div className="mt-4 overflow-x-auto rounded-xl border border-border/60 bg-card">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="text-left">
                <th className="px-4 py-3 font-semibold">Código</th>
                <th className="px-4 py-3 font-semibold">Protocolo</th>
                <th className="px-4 py-3 font-semibold">Data</th>
                <th className="px-4 py-3 font-semibold">Problema</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Ações</th>
              </tr>
            </thead>
            <tbody>
              {tickets.length === 0 ? (
                <tr>
                  <td
                    className="px-4 py-6 text-center text-muted-foreground"
                    colSpan={6}
                  >
                    Você ainda não abriu nenhum chamado.
                  </td>
                </tr>
              ) : (
                tickets.map((t) => (
                  <tr key={t.id} className="border-t border-border/60">
                    <td className="px-4 py-3">{t.codigo}</td>
                    <td className="px-4 py-3">{t.protocolo}</td>
                    <td className="px-4 py-3">
                      {new Date(t.data).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">{t.problema}</td>
                    <td className="px-4 py-3">{t.status}</td>
                    <td className="px-4 py-3">
                      <Button variant="secondary" size="sm">
                        Ver
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Dialog open={successOpen} onOpenChange={setSuccessOpen}>
        <DialogContent className="max-w-md overflow-hidden p-0 border-0 shadow-2xl">
          {lastCreated && (
            <div className="w-full">
              {/* Header com gradiente */}
              <div className="brand-gradient relative overflow-hidden px-6 py-8 text-center">
                <div className="absolute inset-0 opacity-10">
                  <div className="absolute top-0 right-0 w-40 h-40 rounded-full blur-3xl" />
                </div>
                <div className="relative space-y-3">
                  <div className="flex justify-center">
                    <div className="rounded-full bg-white/20 backdrop-blur-sm p-3">
                      <CheckCircle className="w-10 h-10 text-white" />
                    </div>
                  </div>
                  <div>
                    <p className="text-white/80 text-sm font-medium">Sucesso!</p>
                    <h2 className="text-white text-2xl font-extrabold mt-1">Chamado Aberto</h2>
                  </div>
                </div>
              </div>

              {/* Conteúdo */}
              <div className="p-6 space-y-6">
                <p className="text-sm text-muted-foreground text-center">
                  Suas informações foram registradas com sucesso. Guarde estes dados para futuras referências.
                </p>

                {/* Código */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Código do Chamado
                  </label>
                  <div className="relative group">
                    <div className="bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/20 rounded-lg p-4">
                      <div className="font-mono font-bold text-lg text-primary">
                        {lastCreated.codigo}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(lastCreated.codigo);
                        } catch {}
                      }}
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Protocolo */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Número de Protocolo
                  </label>
                  <div className="relative group">
                    <div className="bg-gradient-to-r from-accent/10 to-accent/5 border border-accent/20 rounded-lg p-4">
                      <div className="font-mono font-bold text-lg text-accent">
                        {lastCreated.protocolo}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(lastCreated.protocolo);
                        } catch {}
                      }}
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <Separator className="my-2" />

                {/* Ações */}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(
                          `Código: ${lastCreated.codigo}\nProtocolo: ${lastCreated.protocolo}`,
                        );
                      } catch {}
                    }}
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    Copiar Tudo
                  </Button>
                  <Button
                    className="flex-1"
                    onClick={() => setSuccessOpen(false)}
                  >
                    Concluído
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

    // Validate required fields
    const fieldLabels: Record<string, string> = {
      nome: "Nome do solicitante",
      cargo: "Cargo",
      email: "E-mail",
      telefone: "Telefone",
      unidade: "Unidade",
      problema: "Problema Reportado",
      descricao: "Descrição do problema",
    };

    const requiredFields = ["nome", "cargo", "email", "telefone", "unidade", "problema", "descricao"] as const;
    const missingFields = requiredFields.filter((field) => !form[field].trim());

    if (missingFields.length > 0) {
      const missingLabels = missingFields.map((field) => fieldLabels[field]).join(", ");
      alert(`Campos obrigatórios não preenchidos: ${missingLabels}\n\nOs arquivos são opcionais.`);
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
    [listaProblemas, form.problema],
  );

  const formatTempo = (horas: number | null) => {
    if (!horas) return null;
    if (horas < 24) return `${horas}h`;
    const dias = horas / 24;
    return dias % 1 === 0 ? `${dias}d` : `${horas}h`;
  };

  const getPrioridadeColor = (prioridade: string) => {
    const colors: Record<string, string> = {
      Crítica: "text-red-600 dark:text-red-400",
      Alta: "text-orange-600 dark:text-orange-400",
      Normal: "text-blue-600 dark:text-blue-400",
      Baixa: "text-green-600 dark:text-green-400",
    };
    return colors[prioridade] || colors.Normal;
  };

  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="nome">Nome do solicitante</Label>
        <Input
          id="nome"
          value={form.nome}
          onChange={(e) => setForm({ ...form, nome: e.target.value })}
          required
        />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="grid gap-2">
          <Label htmlFor="cargo">Cargo</Label>
          <Select
            value={form.cargo}
            onValueChange={(v) => setForm({ ...form, cargo: v })}
          >
            <SelectTrigger id="cargo">
              <SelectValue placeholder="Selecione" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Coordenador">Coordenador</SelectItem>
              <SelectItem value="Funcionário">Funcionário</SelectItem>
              <SelectItem value="Gerente">Gerente</SelectItem>
              <SelectItem value="Gerente regional">Gerente regional</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="grid gap-2">
          <Label htmlFor="email">E-mail</Label>
          <Input
            id="email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="telefone">Telefone</Label>
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
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="grid gap-2">
          <Label>Selecione a unidade</Label>
          <Select
            value={form.unidade}
            onValueChange={(v) => setForm({ ...form, unidade: v })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecione" />
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
          <Label>Problema Reportado</Label>
          <Select
            value={form.problema}
            onValueChange={(v) => setForm({ ...form, problema: v })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecione" />
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
        <div className="grid gap-2 p-3 rounded-lg bg-secondary/40 border border-secondary">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Prioridade:</span>
              <span
                className={`font-semibold text-sm ${getPrioridadeColor(selectedProblem.prioridade)}`}
              >
                {selectedProblem.prioridade}
              </span>
            </div>
            {selectedProblem.tempo_resolucao_horas && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Prazo máximo:</span>
                <span className="font-semibold text-sm">
                  {formatTempo(selectedProblem.tempo_resolucao_horas)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {selectedProblem?.requer_internet && (
        <div className="grid gap-2">
          <Label>Selecione o item de Internet</Label>
          <Select
            value={form.internetItem}
            onValueChange={(v) => setForm({ ...form, internetItem: v })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecione" />
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
        <Label htmlFor="descricao">Descrição do problema</Label>
        <textarea
          id="descricao"
          className="min-h-[100px] rounded-md border border-input bg-background p-3 text-sm"
          placeholder="Descreva o que está acontecendo"
          value={form.descricao}
          onChange={(e) => setForm({ ...form, descricao: e.target.value })}
          required
        />
      </div>
      <div className="grid gap-2">
        <Label>Anexar Arquivos (opcional)</Label>
        <FileUploadArea files={files} onChange={setFiles} maxSize={25} />
      </div>
      <div className="flex items-center justify-end gap-3 pt-2">
        <Button type="submit">Salvar</Button>
      </div>
    </form>
  );
}
