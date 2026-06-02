import { useProgress } from "../api.js";

function pct(part, whole) {
  if (!whole) return 0;
  return Math.round((part / whole) * 100);
}

function ProgressCard({ label, done, total, color }) {
  const percent = pct(done, total);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-medium text-slate-600">{label}</p>
        <p className="text-sm font-semibold text-slate-400">{percent}%</p>
      </div>
      <p className="mt-1 text-3xl font-bold text-slate-900">
        {done}
        <span className="text-lg font-medium text-slate-400"> / {total}</span>
      </p>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function StatusPage() {
  const { data, isLoading, isError } = useProgress();

  if (isLoading) return <p className="p-6 text-slate-500">Chargement…</p>;
  if (isError || !data)
    return <p className="p-6 text-red-600">Erreur de connexion à l'API.</p>;

  const fullyTagged = Math.min(data.scored, data.extracted);

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h2 className="text-lg font-bold text-slate-900">État des lieux du tagging IA</h2>
      <p className="mt-1 text-sm text-slate-500">
        Chaque offre passe par Gemini pour un score puis pour l'extraction des champs normés.
        Le quota free tier limite le débit : le reste est traité automatiquement chaque jour.
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <ProgressCard
          label="Offres scorées"
          done={data.scored}
          total={data.total}
          color="bg-emerald-500"
        />
        <ProgressCard
          label="Offres catégorisées"
          done={data.extracted}
          total={data.total}
          color="bg-indigo-500"
        />
        <ProgressCard
          label="Entièrement taguées"
          done={fullyTagged}
          total={data.total}
          color="bg-violet-500"
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Total offres" value={data.total} />
        <Stat label="En file (score)" value={data.pending_scoring} />
        <Stat label="En file (catégorisation)" value={data.pending_extraction} />
        <Stat label="Appels Gemini restants" value={data.remaining_calls} />
      </div>

      <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5">
        <p className="text-sm font-medium text-amber-700">Estimation avant tagging complet</p>
        {data.estimated_days === 0 ? (
          <p className="mt-1 text-2xl font-bold text-emerald-700">✓ Tout est tagué !</p>
        ) : (
          <>
            <p className="mt-1 text-3xl font-bold text-slate-900">
              ≈ {data.estimated_days} jour{data.estimated_days > 1 ? "s" : ""}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {data.remaining_calls} appels restants à ~{data.daily_quota}/jour (quota Gemini).
              Le cron quotidien rattrape le retard automatiquement.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}
