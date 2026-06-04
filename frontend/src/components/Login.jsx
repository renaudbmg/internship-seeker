import { useState } from "react";
import { probeAuth, setToken } from "../api.js";

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    setToken(password);
    const ok = await probeAuth();
    setLoading(false);
    if (ok) {
      onSuccess();
    } else {
      setError("Mot de passe incorrect");
      setPassword("");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div className="mb-6 flex items-center gap-3">
          <img src="/icon-192.png" alt="" className="h-10 w-10 rounded-xl" />
          <div>
            <h1 className="text-lg font-bold text-slate-900">Internship Seeker</h1>
            <p className="text-sm text-slate-500">Accès protégé</p>
          </div>
        </div>

        <label className="mb-1 block text-sm font-medium text-slate-700">Mot de passe</label>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
          placeholder="••••••••"
        />
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading || !password}
          className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "Vérification…" : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
