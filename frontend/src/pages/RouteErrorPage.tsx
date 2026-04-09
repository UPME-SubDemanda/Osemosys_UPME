/**
 * RouteErrorPage - Error boundary de ruta
 *
 * Captura errores de React Router (useRouteError).
 * Si es RouteErrorResponse muestra status y statusText; si es Error muestra message.
 * Botón para recargar la página.
 */
import { useEffect } from "react";
import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { Button } from "@/shared/components/Button";

/** Detecta el error de chunk desactualizado que produce Vite tras un nuevo build. */
function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return (
    error.message.includes("Failed to fetch dynamically imported module") ||
    error.message.includes("Unable to preload CSS") ||
    error.message.includes("Importing a module script failed")
  );
}

export function RouteErrorPage() {
  const error = useRouteError();

  // Si el chunk ya no existe en el servidor (nuevo deploy), recargar
  // automáticamente para que el navegador obtenga el HTML y assets actuales.
  useEffect(() => {
    if (isChunkLoadError(error)) {
      window.location.reload();
    }
  }, [error]);

  let title = "Error";
  let message = "Ocurrió un error al cargar la ruta.";

  if (isRouteErrorResponse(error)) {
    title = `Error ${error.status}`;
    message = error.statusText;
  } else if (error instanceof Error) {
    message = error.message;
  }

  // Mostrar pantalla mínima mientras se recarga (el useEffect dispara reload)
  if (isChunkLoadError(error)) {
    return (
      <div style={{ padding: 24 }}>
        <p style={{ opacity: 0.6 }}>Actualizando la aplicación...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>{title}</h1>
      <p style={{ opacity: 0.85 }}>{message}</p>
      <Button variant="ghost" onClick={() => window.location.reload()}>
        Recargar
      </Button>
    </div>
  );
}

