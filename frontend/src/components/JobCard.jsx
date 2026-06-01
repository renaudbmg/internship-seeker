import { scoreColor, statusMeta } from "../ui.js";

export default function JobCard({ job, selected, onSelect }) {
  const meta = statusMeta(job.status);
  return (
    <button
      onClick={() => onSelect(job)}
      className={`w-full rounded-xl border p-4 text-left transition hover:border-indigo-400 hover:shadow-sm ${
        selected ? "border-indigo-500 bg-indigo-50/40" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-slate-900">{job.title}</h3>
          <p className="truncate text-sm text-slate-600">
            {job.company} · {job.location || "—"}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-lg px-2 py-1 text-sm font-bold ${scoreColor(job.score_ai)}`}
        >
          {job.score_ai ?? "—"}
        </span>
      </div>
      {job.summary_ai && (
        <p className="mt-2 line-clamp-2 text-sm text-slate-500">{job.summary_ai}</p>
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
      </div>
    </button>
  );
}
