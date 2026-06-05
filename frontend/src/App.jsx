import { useState } from "react";
import { clearToken, useJobs, useTriggerScrape } from "./api.js";
import StatsBar from "./components/StatsBar.jsx";
import Filters from "./components/Filters.jsx";
import JobCard from "./components/JobCard.jsx";
import JobDetail from "./components/JobDetail.jsx";
import StatusPage from "./components/StatusPage.jsx";
import Charts from "./components/Charts.jsx";

const TABS = [
  { value: "jobs", label: "Offres" },
  { value: "charts", label: "Graphiques" },
  { value: "status", label: "État des lieux" },
];

export default function App() {
  const [view, setView] = useState("jobs");
  const [filters, setFilters] = useState({ search: "", status: "", score_min: "", hidden: "", unseen: "" });
  const [selectedId, setSelectedId] = useState(null);
  const { data, isLoading, isError } = useJobs(filters);
  const triggerScrape = useTriggerScrape();

  const items = data?.items || [];
  const selected = items.find((j) => j.id === selectedId) || null;

  return (
    <div className="flex h-screen flex-col bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Internship Seeker</h1>
            <p className="text-sm text-slate-500">
              PFE / stage sport & data — mars 2026
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => triggerScrape.mutate()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              {triggerScrape.isPending ? "Lancement…" : "Scraper maintenant"}
            </button>
            <button
              onClick={() => { clearToken(); window.location.reload(); }}
              title="Se déconnecter"
              className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200"
            >
              ⏏
            </button>
          </div>
        </div>
        {triggerScrape.isSuccess && (
          <p className="mt-2 text-sm text-green-600">
            Scrape lancé en arrière-plan — rafraîchis dans quelques instants.
          </p>
        )}
        <div className="mt-4 flex gap-2">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setView(tab.value)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                view === tab.value
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {view === "jobs" && (
          <div className="mt-4 hidden lg:block">
            <StatsBar />
          </div>
        )}
      </header>

      {view === "status" ? (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <StatusPage />
        </main>
      ) : view === "charts" ? (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Charts />
        </main>
      ) : (
        <>
          <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[1fr_minmax(360px,40%)]">
            <section className="overflow-y-auto">
              {/* Filtres dans le flux scrollable : ils défilent avec la liste sur
                  mobile (gain de place), mais restent épinglés en haut sur desktop. */}
              <div className="border-b border-slate-200 bg-white px-6 py-3 lg:sticky lg:top-0 lg:z-10">
                <Filters filters={filters} onChange={setFilters} />
              </div>
              <div className="p-6">
                {isLoading && <p className="text-slate-500">Chargement…</p>}
                {isError && (
                  <p className="text-red-600">Erreur de connexion à l'API (port 8000).</p>
                )}
                {!isLoading && items.length === 0 && (
                  <p className="text-slate-500">Aucune offre ne correspond aux filtres.</p>
                )}
                <div className="flex flex-col gap-3">
                  {items.map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      selected={job.id === selectedId}
                      onSelect={(j) => setSelectedId(j.id)}
                    />
                  ))}
                </div>
              </div>
            </section>

            {selected && <JobDetail job={selected} onClose={() => setSelectedId(null)} />}
          </main>
        </>
      )}
    </div>
  );
}
