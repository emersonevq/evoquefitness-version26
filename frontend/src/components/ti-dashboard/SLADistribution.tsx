import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

interface SLADistributionProps {
  dentroDaSla: number;
  foraDaSla: number;
  loading?: boolean;
}

export function SLADistribution({
  dentroDaSla,
  foraDaSla,
  loading,
}: SLADistributionProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-border/60 bg-card p-6 h-80 flex items-center justify-center">
        <p className="text-muted-foreground">Carregando dados...</p>
      </div>
    );
  }

  const total = dentroDaSla + foraDaSla;
  if (total === 0) {
    return (
      <div className="rounded-xl border border-border/60 bg-card p-6 h-80 flex flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Nenhum chamado ativo</p>
      </div>
    );
  }

  const data = [
    { name: "Dentro SLA", value: dentroDaSla },
    { name: "Fora SLA", value: foraDaSla },
  ];

  const COLORS = ["#22c55e", "#ef4444"];

  return (
    <div className="rounded-xl border border-border/60 bg-card p-6">
      <h3 className="text-lg font-semibold mb-6">Distribuição SLA</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={true}
            label={({ name, value, percent }) =>
              `${name}: ${value} (${(percent * 100).toFixed(0)}%)`
            }
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
            }}
            labelStyle={{ color: "var(--foreground)" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
