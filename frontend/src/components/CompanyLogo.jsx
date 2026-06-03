import { useState } from "react";

// Palette douce, choisie de façon déterministe d'après le nom → même entreprise = même couleur.
const COLORS = [
  "bg-rose-500",
  "bg-orange-500",
  "bg-amber-500",
  "bg-emerald-500",
  "bg-teal-500",
  "bg-sky-500",
  "bg-indigo-500",
  "bg-violet-500",
  "bg-fuchsia-500",
  "bg-slate-500",
];

function initials(name) {
  const words = (name || "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function colorFor(name) {
  let hash = 0;
  for (let i = 0; i < (name || "").length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  return COLORS[Math.abs(hash) % COLORS.length];
}

// Avatar entreprise : vrai logo si `src` dispo et chargeable, sinon repli initiales colorées.
// `size` en px (carré). Utilisé dans la liste (sm) et le panneau détail (lg).
export default function CompanyLogo({ src, company, size = 40 }) {
  const [failed, setFailed] = useState(false);
  const style = { width: size, height: size };

  if (src && !failed) {
    return (
      <img
        src={src}
        alt={company || ""}
        style={style}
        onError={() => setFailed(true)}
        className="shrink-0 rounded-lg border border-slate-200 bg-white object-contain"
      />
    );
  }

  return (
    <div
      style={style}
      className={`flex shrink-0 items-center justify-center rounded-lg font-bold text-white ${colorFor(
        company,
      )}`}
    >
      <span style={{ fontSize: size * 0.4 }}>{initials(company)}</span>
    </div>
  );
}
