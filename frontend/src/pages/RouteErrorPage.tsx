/**
 * RouteErrorPage - Error boundary de ruta
 *
 * Captura errores de React Router (useRouteError).
 * Si es RouteErrorResponse muestra status y statusText; si es Error muestra message.
 * Botón para recargar la página.
 */
import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { Button } from "@/shared/components/Button";

export function RouteErrorPage() {
  const error = useRouteError();

  let title = "Error";
  let message = "Ocurrió un error al cargar la ruta.";

  // Determinar título y mensaje según tipo de error
  if (isRouteErrorResponse(error)) {
    title = `Error ${error.status}`;
    message = error.statusText;
  } else if (error instanceof Error) {
    message = error.message;
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

