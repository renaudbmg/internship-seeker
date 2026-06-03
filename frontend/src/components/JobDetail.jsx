import { useEffect, useState } from "react";
import { useUpdateNotes, useUpdateStatus, useUpdateTracking } from "../api.js";
import { RESPONSES, STATUSES, followUpDue, formatDate, scoreColor, toDateInput } from "../ui.js";
import CompanyLogo from "./CompanyLogo.jsx";

export default function JobDetail({ job, onClose }) {
  const [notes, setNotes] = useState(job.notes || "");
  const updateStatus = useUpdateStatus();
  const updateNotes = useUpdateNotes();

  useEffect(() => setNotes(job.notes || ""), [job.id]);

  if (!job) return null;

  return (
    <aside className="flex h-full flex-col gap-4 overflow-y-auto border-l border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <CompanyLogo src={job.logo_url} company={job.company} size={48} />
          <div>
            <h2 className="text-lg font-bold text-slate-900">{job.title}</h2>
            <p className="text-sm text-slate-600">
              {job.company} · {job.location || "—"}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100"
        >
          ✕
        </button>
      </div>

      <div className="flex items-center gap-3">
        <span className={`rounded-lg px-3 py-1 font-bold ${scoreColor(job.score_ai)}`}>
          Score {job.score_ai ?? "—"}
        </span>
        <a
          href={job.url}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg bg-indigo-600 px-3 py-1 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Voir l'offre ↗
        </a>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <button
            key={s.value}
            onClick={() => updateStatus.mutate({ id: job.id, status: s.value })}
            className={`rounded-lg px-3 py-1 text-sm ${
              job.status === s.value
                ? "ring-2 ring-indigo-500 " + s.color
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {job.status === "applied" && <JobTracking job={job} />}

      {job.details_ai && <JobFiche details={job.details_ai} />}

      <div>
        <label className="mb-1 block text-sm font-semibold text-slate-700">Notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-slate-300 p-2 text-sm"
        />
        <button
          onClick={() => updateNotes.mutate({ id: job.id, notes })}
          className="mt-2 rounded-lg bg-slate-800 px-3 py-1 text-sm text-white hover:bg-slate-900"
        >
          {updateNotes.isPending ? "Enregistrement…" : "Enregistrer les notes"}
        </button>
      </div>

      <div>
        <p className="mb-1 text-sm font-semibold text-slate-700">Description</p>
        <p className="whitespace-pre-wrap text-sm text-slate-600">
          {job.description || "Pas de description récupérée."}
        </p>
      </div>
    </aside>
  );
}

function JobTracking({ job }) {
  const updateTracking = useUpdateTracking();
  const due = followUpDue(job);

  const setFollowUp = (value) =>
    updateTracking.mutate({
      id: job.id,
      follow_up_at: value || null,
      response: job.response || "pending",
    });

  const setResponse = (value) =>
    updateTracking.mutate({
      id: job.id,
      follow_up_at: job.follow_up_at || null,
      response: value,
    });

  return (
    <div className="rounded-lg border border-green-200 bg-green-50/50 p-3 text-sm">
      <p className="mb-2 font-semibold text-green-700">Suivi de candidature</p>

      <p className="mb-3 text-slate-600">
        Postulé le <span className="font-medium">{formatDate(job.applied_at) || "—"}</span>
      </p>

      <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
        Date de relance
      </label>
      <input
        type="date"
        value={toDateInput(job.follow_up_at)}
        onChange={(e) => setFollowUp(e.target.value)}
        className="mb-1 w-full rounded-lg border border-slate-300 p-1.5 text-sm"
      />
      {due && (
        <p className="mb-3 font-medium text-amber-700">⏰ Relance à faire</p>
      )}

      <p className="mb-1 mt-3 text-xs uppercase tracking-wide text-slate-400">Réponse</p>
      <div className="flex flex-wrap gap-1.5">
        {RESPONSES.map((r) => (
          <button
            key={r.value}
            onClick={() => setResponse(r.value)}
            className={`rounded-lg px-2.5 py-1 text-xs ${
              (job.response || "pending") === r.value
                ? "ring-2 ring-green-500 " + r.color
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const FACTS = [
  ["type_contrat", "Contrat"],
  ["duree", "Durée"],
  ["date_debut", "Début"],
  ["remuneration", "Rémunération"],
  ["lieu", "Lieu"],
  ["teletravail", "Télétravail"],
  ["profil", "Profil"],
  ["secteur", "Secteur"],
];

const filled = (v) => v && v !== "Non précisé";

function JobFiche({ details }) {
  const facts = FACTS.filter(([key]) => filled(details[key]));
  const missions = Array.isArray(details.missions) ? details.missions : [];
  const competences = Array.isArray(details.competences) ? details.competences : [];

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
      <p className="mb-2 font-semibold text-indigo-700">Fiche IA</p>

      {facts.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
          {facts.map(([key, label]) => (
            <div key={key}>
              <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
              <dd className="font-medium text-slate-700">{details[key]}</dd>
            </div>
          ))}
        </dl>
      )}

      {competences.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Compétences</p>
          <div className="flex flex-wrap gap-1.5">
            {competences.map((c, i) => (
              <span
                key={i}
                className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700"
              >
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {missions.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Missions</p>
          <ul className="list-disc space-y-1 pl-5 text-slate-700">
            {missions.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
