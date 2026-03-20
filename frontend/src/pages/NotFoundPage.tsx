/**
 * NotFoundPage - Página 404
 *
 * Se muestra cuando la ruta solicitada no existe.
 * Incluye enlace para volver al inicio (paths.app).
 */
import { Link } from "react-router-dom";
import { paths } from "@/routes/paths";
import { Button } from "@/shared/components/Button";

export function NotFoundPage() {
  return (
    <div style={{ padding: 24 }}>
      <h1>Página no encontrada</h1>
      <p style={{ opacity: 0.85 }}>La ruta solicitada no existe.</p>
      <Link to={paths.app} style={{ textDecoration: "none" }}>
        <Button variant="primary">Volver al inicio</Button>
      </Link>
    </div>
  );
}

