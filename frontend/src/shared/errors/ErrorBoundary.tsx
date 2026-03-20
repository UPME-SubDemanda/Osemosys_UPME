/**
 * Error boundary React. Captura errores en el árbol de hijos y muestra UI de fallback.
 * componentDidCatch es el punto para integrar Sentry/OTel en producción.
 */
import type { ReactNode } from "react";
import { Component } from "react";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
  error?: Error;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  /** Actualiza estado para mostrar UI de error en lugar del árbol que falló */
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error) {
    // Punto central para integrar Sentry/OTel en producción.
    // console.error(error);
    void error;
  }

  override render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div style={{ padding: 24 }}>
        <h1>Ocurrió un error inesperado</h1>
        <p>Intenta recargar la página. Si persiste, contacta soporte.</p>
      </div>
    );
  }
}

