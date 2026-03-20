/**
 * Contenedor tipo tarjeta para agrupar contenido relacionado.
 * Aplica estilos de borde y fondo definidos en CSS (.card).
 */
import type { ReactNode } from "react";

export function Card({ children }: { children: ReactNode }) {
  return (
    <div className="card">{children}</div>
  );
}

