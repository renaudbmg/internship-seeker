import { useStats } from "../api.js";
import { statusMeta } from "../ui.js";

export default function StatsBar() {
  const { data } = useStats();
  if (!data) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="rounded-full bg-slate-800 px-3 py-1 font-semibold text-white">
        {data.total} offres
      </span>
      {Object.entries(data.by_status).map(([status, count]) => {
        const meta = statusMeta(status);
        return (
          <span key={status} className={`rounded-full px-3 py-1 ${meta.color}`}>
            {meta.label} · {count}
          </span>
        );
      })}
      {Object.entries(data.by_source).map(([source, count]) => (
        <span
          key={source}
          className="rounded-full bg-indigo-50 px-3 py-1 text-indigo-700"
        >
          {source} · {count}
        </span>
      ))}
    </div>
  );
}
