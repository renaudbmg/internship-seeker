import { useState } from "react";
import { downloadCandidaturesCsv } from "../api.js";
import { STATUSES } from "../ui.js";

export default function Filters({ filters, onChange }) {
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });
  const toggle = (key, on = "true") => () =>
    onChange({ ...filters, [key]: filters[key] ? "" : on });
  const [exporting, setExporting] = useState(false);

  const exportCsv = async () => {
    setExporting(true);
    try {
      await downloadCandidaturesCsv();
    } catch (e) {
      alert(e.message);
    } finally {
      setExporting(false);
    }
  };

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
      <button
        onClick={toggle("unseen")}
        className={`rounded-lg px-3 py-2 text-sm font-medium ${
          filters.unseen
            ? "bg-indigo-600 text-white"
            : "bg-slate-100 text-slate-600 hover:bg-slate-200"
        }`}
      >
        ✨ Nouveautés
      </button>
      <button
        onClick={exportCsv}
        disabled={exporting}
        className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 disabled:opacity-50"
      >
        {exporting ? "Export…" : "📥 Export CSV"}
      </button>
      <button
        onClick={toggle("hidden")}
        className={`rounded-lg px-3 py-2 text-sm font-medium ${
          filters.hidden
            ? "bg-slate-800 text-white"
            : "bg-slate-100 text-slate-600 hover:bg-slate-200"
        }`}
      >
        {filters.hidden ? "← Annonces actives" : "🗑 Corbeille"}
      </button>
    </div>
  );
}
