import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

// En prod (Vercel) VITE_API_BASE="" → URLs relatives (même domaine, pas de CORS).
// En dev VITE_API_BASE non défini → fallback localhost:8000.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const TOKEN_KEY = "is_auth_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY) || "";
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (res.status === 401) {
    // Token invalide/expiré → on purge et on renvoie à l'écran de login.
    clearToken();
    window.location.reload();
    throw new Error("401 Non autorisé");
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// Probe d'authentification : true si l'accès est autorisé (auth désactivée OU token
// valide), false si un mot de passe est requis et manquant/invalide.
export async function probeAuth() {
  const token = getToken();
  try {
    const res = await fetch(`${API_BASE}/auth/check`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return res.ok;
  } catch {
    return false;
  }
}

// Télécharge l'export CSV des candidatures (fetch authentifié → blob → download).
export async function downloadCandidaturesCsv() {
  const token = getToken();
  const res = await fetch(`${API_BASE}/jobs/export.csv`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Export échoué (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "candidatures.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ── Notifications push PWA ───────────────────────────────────────────────────
function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function pushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

// Active les notifications : SW + permission + abonnement + envoi au backend.
// Renvoie un message d'état (affiché à l'utilisateur).
export async function enablePush() {
  if (!pushSupported()) throw new Error("Push non supporté sur cet appareil/navigateur");
  const { key } = await request("/push/vapid-public-key");
  if (!key) throw new Error("Push non configuré côté serveur (clés VAPID manquantes)");

  const reg = await navigator.serviceWorker.register("/sw.js");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Permission refusée");

  await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  });
  await request("/push/subscribe", { method: "POST", body: JSON.stringify(sub.toJSON()) });
  return "Notifications activées ✅";
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
    // Garde la liste précédente affichée pendant le chargement du nouveau filtre
    // → pas de flash « Chargement… », transition fluide entre recherches/filtres.
    placeholderData: keepPreviousData,
  });
}

// Détail complet d'une offre (avec description). Appelé à l'ouverture du panneau.
// Le serveur marque l'offre comme vue (seen=true) ; on reflète ça dans la liste
// pour faire disparaître le badge « nouveau » et mettre à jour le filtre Nouveautés.
export function useJob(id) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["job", id],
    enabled: !!id,
    queryFn: async () => {
      const job = await request(`/jobs/${id}`);
      patchJobInCache(qc, id, { seen: true });
      return job;
    },
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
    // Reflète côté UI le nettoyage du suivi fait par le backend selon le statut cible
    // (sinon le badge « relance » reste affiché jusqu'au prochain refetch).
    buildPatch: ({ status }) => {
      if (status === "to_review" || status === "interested")
        return { status, applied_at: null, follow_up_at: null, response: null };
      if (status === "rejected") return { status, follow_up_at: null };
      return { status };
    },
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

// Masque/restaure une annonce. Optimiste : l'offre disparaît immédiatement de la
// liste courante (qu'on soit dans les actives ou dans la corbeille).
export function useSetHidden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, hidden }) =>
      request(`/jobs/${id}/hidden`, { method: "PATCH", body: JSON.stringify({ hidden }) }),
    onMutate: async ({ id }) => {
      await qc.cancelQueries({ queryKey: ["jobs"] });
      const previous = qc.getQueriesData({ queryKey: ["jobs"] });
      qc.setQueriesData({ queryKey: ["jobs"] }, (old) => {
        if (!old?.items) return old;
        const items = old.items.filter((j) => j.id !== id);
        return { ...old, items, total: Math.max(0, (old.total ?? items.length) - 1) };
      });
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.previous?.forEach(([key, data]) => qc.setQueryData(key, data));
    },
    onSettled: () => {
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
