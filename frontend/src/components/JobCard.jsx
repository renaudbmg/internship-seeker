import { useSetHidden } from "../api.js";
import { effectiveScore, followUpDue, scoreColor, statusMeta } from "../ui.js";
import CompanyLogo from "./CompanyLogo.jsx";

const filled = (v) => v && v !== "Non précisé";

// Faits clés de la Fiche IA affichés en puces sur la carte pour comparer sans ouvrir.
function ficheChips(details) {
  if (!details) return [];
  return [details.type_contrat, details.duree, details.teletravail].filter(filled);
}

export default function JobCard({ job, selected, onSelect }) {
  const meta = statusMeta(job.status);
  const chips = ficheChips(job.details_ai);
  const score = effectiveScore(job);
  const setHidden = useSetHidden();

  const toggleHidden = (e) => {
    e.stopPropagation(); // ne pas sélectionner la carte
    setHidden.mutate({ id: job.id, hidden: !job.hidden });
  };
  return (
    <button
      onClick={() => onSelect(job)}
      className={`w-full rounded-xl border p-4 text-left transition hover:border-indigo-400 hover:shadow-sm ${
        selected ? "border-indigo-500 bg-indigo-50/40" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <CompanyLogo src={job.logo_url} company={job.company} size={40} />
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-slate-900">{job.title}</h3>
            <p className="truncate text-sm text-slate-600">
              {job.company} · {job.location || "—"}
            </p>
          </div>
        </div>
        <span
          className={`shrink-0 rounded-lg px-2 py-1 text-sm font-bold ${scoreColor(score.value)} ${
            score.provisional ? "opacity-60" : ""
          }`}
          title={score.provisional ? "Score provisoire (heuristique) — affiné par l'IA bientôt" : "Score IA"}
        >
          {score.value ?? "—"}
          {score.provisional && <span className="ml-0.5 text-[10px] font-normal">~</span>}
        </span>
      </div>
      {chips.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {chips.map((c, i) => (
            <span
              key={i}
              className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
            >
              {c}
            </span>
          ))}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs ${meta.color}`}>{meta.label}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
          {job.source}
        </span>
        {!job.seen && (
          <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-xs text-white">
            nouveau
          </span>
        )}
        {followUpDue(job) && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            ⏰ relance
          </span>
        )}
        <span
          role="button"
          tabIndex={0}
          onClick={toggleHidden}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && toggleHidden(e)}
          title={job.hidden ? "Restaurer l'annonce" : "Masquer l'annonce"}
          className="ml-auto rounded-full px-2 py-0.5 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        >
          {job.hidden ? "↩ Restaurer" : "🗑 Masquer"}
        </span>
      </div>
    </button>
  );
}
