import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App.jsx";
import AuthGate from "./components/AuthGate.jsx";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Données considérées fraîches 1 min → changer d'onglet n'entraîne plus de
      // refetch (les données reviennent du cache instantanément).
      staleTime: 60_000,
      // Pas de refetch automatique au retour sur l'onglet (évitait des allers-retours
      // Turso à chaque fois qu'on revient sur l'app).
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthGate>
        <App />
      </AuthGate>
    </QueryClientProvider>
  </React.StrictMode>
);
