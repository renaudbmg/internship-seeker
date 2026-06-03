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

export function useUpdateStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }) =>
      request(`/jobs/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useUpdateNotes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }) =>
      request(`/jobs/${id}/notes`, {
        method: "PATCH",
        body: JSON.stringify({ notes }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useUpdateTracking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, follow_up_at, response }) =>
      request(`/jobs/${id}/tracking`, {
        method: "PATCH",
        body: JSON.stringify({ follow_up_at, response }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useTriggerScrape() {
  return useMutation({
    mutationFn: () => request("/jobs/trigger-scrape", { method: "POST" }),
  });
}
