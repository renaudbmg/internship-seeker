import { STATUSES } from "../ui.js";

export default function Filters({ filters, onChange }) {
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="text"
        placeholder="Rechercher (titre, entreprise, description)…"
        value={filters.search}
        onChange={set("search")}
        className="min-w-[260px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
      />
      <select
        value={filters.status}
        onChange={set("status")}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
      >
        <option value="">Tous statuts</option>
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      <label className="flex items-center gap-2 text-sm text-slate-600">
        Score min
        <input
          type="number"
          min="0"
          max="100"
          value={filters.score_min}
          onChange={set("score_min")}
          className="w-20 rounded-lg border border-slate-300 px-2 py-2 text-sm"
        />
      </label>
    </div>
  );
}
