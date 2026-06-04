export const STATUSES = [
  { value: "to_review", label: "À traiter", color: "bg-slate-200 text-slate-700" },
  { value: "interested", label: "Intéressé", color: "bg-blue-100 text-blue-700" },
  { value: "applied", label: "Postulé", color: "bg-green-100 text-green-700" },
  { value: "rejected", label: "Rejeté", color: "bg-red-100 text-red-700" },
];

export function statusMeta(value) {
  return STATUSES.find((s) => s.value === value) || STATUSES[0];
}

export function scoreColor(score) {
  if (score == null) return "bg-slate-100 text-slate-400";
  if (score >= 80) return "bg-emerald-500 text-white";
  if (score >= 60) return "bg-lime-500 text-white";
  if (score >= 40) return "bg-amber-500 text-white";
  return "bg-slate-300 text-slate-700";
}

// Score effectif : IA si disponible, sinon score heuristique provisoire (étage 1).
// `provisional` = true quand seul l'heuristique est dispo (Gemini pas encore passé).
export function effectiveScore(job) {
  if (job?.score_ai != null) return { value: job.score_ai, provisional: false };
  if (job?.score_heuristic != null) return { value: job.score_heuristic, provisional: true };
  return { value: null, provisional: false };
}

export const RESPONSES = [
  { value: "pending", label: "En attente", color: "bg-slate-100 text-slate-600" },
  { value: "positive", label: "Réponse positive", color: "bg-green-100 text-green-700" },
  { value: "negative", label: "Refus", color: "bg-red-100 text-red-700" },
  { value: "ghosted", label: "Sans réponse", color: "bg-amber-100 text-amber-700" },
];

export function responseMeta(value) {
  return RESPONSES.find((r) => r.value === value) || RESPONSES[0];
}

// Formate une date ISO en JJ/MM/AAAA (ou "" si nulle).
export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// Convertit une date ISO en valeur d'input type="date" (AAAA-MM-JJ).
export function toDateInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toISOString().slice(0, 10);
}

// Vrai si une relance est due : date passée et réponse encore en attente.
export function followUpDue(job) {
  if (!job?.follow_up_at) return false;
  if (job.response && job.response !== "pending") return false;
  return new Date(job.follow_up_at) <= new Date();
}
