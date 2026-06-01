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
