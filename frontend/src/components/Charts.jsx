import { useStats } from "../api.js";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from "recharts";

const SOURCE_COLORS = {
  linkedin: "#0A66C2",
  wttj: "#4553FF",
  jobteaser: "#FF5C35",
  smartrecruiters: "#1dbf73",
  greenhouse: "#3db384",
  workday: "#f97316",
  themuse: "#8b5cf6",
};

const STATUS_COLORS = {
  to_review: "#94a3b8",
  interested: "#3b82f6",
  applied: "#22c55e",
  rejected: "#ef4444",
};

const STATUS_LABELS = {
  to_review: "À voir",
  interested: "Intéressé",
  applied: "Candidaté",
  rejected: "Refusé",
};

function ChartCard({ title, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-slate-700">{title}</h3>
      {children}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-md text-sm">
      <p className="font-medium text-slate-700">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.fill || p.color }}>
          {p.value} offre{p.value > 1 ? "s" : ""}
        </p>
      ))}
    </div>
  );
}

function StatusChart({ byStatus }) {
  const data = Object.entries(byStatus)
    .filter(([, v]) => v > 0)
    .map(([status, count]) => ({
      name: STATUS_LABELS[status] || status,
      value: count,
      fill: STATUS_COLORS[status] || "#94a3b8",
    }));
  if (!data.length)
    return <p className="text-sm text-slate-400 text-center py-8">Aucune donnée</p>;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={70}
          label={({ name, percent }) =>
            percent > 0.05 ? `${name} ${Math.round(percent * 100)}%` : ""
          }
          labelLine={false}
        >
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
        </Pie>
        <Legend
          formatter={(value) => (
            <span className="text-xs text-slate-600">{value}</span>
          )}
        />
        <Tooltip
          formatter={(value) => [`${value} offre${value > 1 ? "s" : ""}`, ""]}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

function SourceChart({ bySource }) {
  const data = Object.entries(bySource)
    .sort((a, b) => b[1] - a[1])
    .map(([source, count]) => ({ source, count }));
  if (!data.length)
    return <p className="text-sm text-slate-400 text-center py-8">Aucune donnée</p>;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 24, bottom: 4, left: 60 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="source"
          tick={{ fontSize: 11 }}
          width={56}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="count" radius={[0, 4, 4, 0]}>
          {data.map((entry, i) => (
            <Cell
              key={i}
              fill={SOURCE_COLORS[entry.source] || "#6366f1"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function TimelineChart({ byDay }) {
  const data = Object.entries(byDay).map(([date, count]) => ({
    date: date.slice(5),
    count,
  }));
  if (data.length < 2)
    return (
      <p className="text-sm text-slate-400 text-center py-8">
        Données insuffisantes (au moins 2 jours requis)
      </p>
    );

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          formatter={(value) => [`${value} offre${value > 1 ? "s" : ""}`, "Nouvelles offres"]}
          labelFormatter={(label) => `Date : ${label}`}
        />
        <Line
          type="monotone"
          dataKey="count"
          stroke="#6366f1"
          strokeWidth={2}
          dot={{ r: 3, fill: "#6366f1" }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function TaggedChart({ byTagged }) {
  const data = Object.entries(byTagged).map(([date, count]) => ({
    date: date.slice(5),
    count,
  }));
  if (data.length < 1)
    return (
      <p className="text-sm text-slate-400 text-center py-8">
        Aucune offre taguée pour le moment
      </p>
    );

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          formatter={(value) => [`${value} offre${value > 1 ? "s" : ""}`, "Tags Gemini"]}
          labelFormatter={(label) => `Date : ${label}`}
        />
        <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function Charts() {
  const { data, isLoading, isError } = useStats();

  if (isLoading)
    return <p className="p-8 text-center text-slate-500">Chargement des stats…</p>;
  if (isError)
    return (
      <p className="p-8 text-center text-red-500">
        Erreur de connexion à l'API (port 8000).
      </p>
    );
  if (!data) return null;

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ChartCard title="📋 Répartition par statut">
          <StatusChart byStatus={data.by_status || {}} />
        </ChartCard>

        <ChartCard title="🔍 Offres par source">
          <SourceChart bySource={data.by_source || {}} />
        </ChartCard>

        <ChartCard title="📈 Nouvelles offres par jour">
          <TimelineChart byDay={data.by_day || {}} />
        </ChartCard>

        <ChartCard title="🤖 Tags Gemini par jour">
          <TaggedChart byTagged={data.by_tagged || {}} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Total offres", value: data.total },
          { label: "Sources actives", value: Object.keys(data.by_source || {}).length },
          {
            label: "Tags aujourd'hui",
            value: (() => {
              const today = new Date().toISOString().slice(0, 10);
              return data.by_tagged?.[today] || 0;
            })(),
          },
          {
            label: "Candidaturés",
            value: data.by_status?.applied || 0,
          },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 text-center shadow-sm">
            <p className="text-2xl font-bold text-slate-900">{value}</p>
            <p className="mt-1 text-xs text-slate-500">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
