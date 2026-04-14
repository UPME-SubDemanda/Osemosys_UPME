import React from "react";
import ReactDOM from "react-dom/client";
import "@/app/styles/global.css";
/** Registra exporting / offline-exporting antes de cualquier gráfica (un solo bundle Highcharts). */
import "@/shared/charts/highchartsSetup";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("No se encontro el elemento root.");
}
const root = rootElement as HTMLElement;

async function bootstrap() {
  try {
    const [{ AppProviders }, { App }] = await Promise.all([
      import("@/app/providers/AppProviders"),
      import("@/app/App"),
    ]);

    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <AppProviders>
          <App />
        </AppProviders>
      </React.StrictMode>,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Error desconocido al iniciar la app.";
    root.innerHTML = `<div style="padding:24px;color:#fff;font-family:system-ui;">
      <h2 style="margin-top:0;">Error al iniciar frontend</h2>
      <p style="opacity:.9;">${message}</p>
      <p style="opacity:.75;">Abre consola del navegador para mas detalles.</p>
    </div>`;
    console.error(error);
  }
}

void bootstrap();
