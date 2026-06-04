import { useEffect, useState } from "react";
import { probeAuth } from "../api.js";
import Login from "./Login.jsx";

// Affiche l'app uniquement si l'accès est autorisé (auth désactivée côté serveur
// OU mot de passe valide). Sinon, écran de login. Les hooks de données de l'app
// ne se montent qu'une fois `authed` = true.
export default function AuthGate({ children }) {
  const [authed, setAuthed] = useState(null); // null = vérification en cours

  useEffect(() => {
    probeAuth().then(setAuthed);
  }, []);

  if (authed === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-400">
        Chargement…
      </div>
    );
  }

  if (!authed) {
    return <Login onSuccess={() => setAuthed(true)} />;
  }

  return children;
}
