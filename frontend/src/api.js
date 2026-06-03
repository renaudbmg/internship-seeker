import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

// En prod (Vercel) VITE_API_BASE="" → URLs relatives (même domaine, pas de CORS).
// En dev VITE_API_BASE non défini → fallback localhost:8000.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function buildQuery(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== "" && v !== null && v !== undefined) params.append(k, v);
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useJobs(filters) {
  return useQuery({
    queryKey: ["jobs", filters],
    queryFn: () => request(`/jobs${buildQuery(filters)}`),
  });
}

export function useStats() {
  return useQuery({ queryKey: ["stats"], queryFn: () => request("/jobs/stats") });
}

export function useProgress() {
  return useQuery({ queryKey: ["progress"], queryFn: () => request("/jobs/progress") });
}

// Met à jour instantanément l'offre {id} dans tous les caches de liste ["jobs", …],
// en appliquant `patch` (les champs modifiés). Renvoie le snapshot pour rollback.
function patchJobInCache(qc, id, patch) {
  const previous = qc.getQueriesData({ queryKey: ["jobs"] });
  qc.setQueriesData({ queryKey: ["jobs"] }, (old) => {
    if (!old?.items) return old;
    return {
      ...old,
      items: old.items.map((j) => (j.id === id ? { ...j, ...patch } : j)),
    };
  });
  return previous;
}

// Fabrique une mutation « optimiste » : l'UI reflète le changement immédiatement
// (onMutate), rollback en cas d'erreur, et resync discrète en arrière-plan (onSettled).
function makeOptimisticMutation(qc, { mutationFn, buildPatch, invalidateStats }) {
  return useMutation({
    mutationFn,
    onMutate: async (vars) => {
      await qc.cancelQueries({ queryKey: ["jobs"] });
      const previous = patchJobInCache(qc, vars.id, buildPatch(vars));
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.previous?.forEach(([key, data]) => qc.setQueryData(key, data));
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      if (invalidateStats) qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useUpdateStatus() {
  const qc = useQueryClient();
  return makeOptimisticMutation(qc, {
    mutationFn: ({ id, status }) =>
      request(`/jobs/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
    buildPatch: ({ status }) => ({ status }),
    invalidateStats: true,
  });
}

export function useUpdateNotes() {
  const qc = useQueryClient();
  return makeOptimisticMutation(qc, {
    mutationFn: ({ id, notes }) =>
      request(`/jobs/${id}/notes`, { method: "PATCH", body: JSON.stringify({ notes }) }),
    buildPatch: ({ notes }) => ({ notes }),
  });
}

export function useUpdateTracking() {
  const qc = useQueryClient();
  return makeOptimisticMutation(qc, {
    mutationFn: ({ id, follow_up_at, response }) =>
      request(`/jobs/${id}/tracking`, {
        method: "PATCH",
        body: JSON.stringify({ follow_up_at, response }),
      }),
    buildPatch: ({ follow_up_at, response }) => ({ follow_up_at, response }),
    invalidateStats: true,
  });
}

export function useTriggerScrape() {
  return useMutation({
    mutationFn: () => request("/jobs/trigger-scrape", { method: "POST" }),
  });
}
