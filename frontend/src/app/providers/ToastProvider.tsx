/**
 * Provider de notificaciones toast. Muestra mensajes temporales en esquina inferior derecha.
 * Cada toast se auto-elimina tras 3.5s. Soporta variantes info, success, error.
 */
import type { ReactNode } from "react";
import { useCallback, useMemo, useState } from "react";
import { ToastContext, type ToastKind } from "@/app/providers/ToastContext";

type ToastItem = {
  id: string;
  message: string;
  kind: ToastKind;
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const remove = useCallback((id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  /** Añade un toast; se elimina automáticamente tras 3.5 segundos */
  const push = useCallback((message: string, kind: ToastItem["kind"] = "info") => {
    const id = Math.random().toString(36).slice(2, 10);
    setItems((prev) => [...prev, { id, message, kind }]);
    window.setTimeout(() => remove(id), 3500);
  }, [remove]);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div style={{ position: "fixed", right: 16, bottom: 16, display: "grid", gap: 8, zIndex: 400 }}>
        {items.map((item) => (
          <div
            key={item.id}
            style={{
              minWidth: 280,
              maxWidth: 440,
              padding: "10px 12px",
              borderRadius: 12,
              border:
                item.kind === "error"
                  ? "1px solid rgba(239,68,68,0.45)"
                  : item.kind === "success"
                    ? "1px solid rgba(34,197,94,0.45)"
                    : "1px solid rgba(56,189,248,0.45)",
              background:
                item.kind === "error"
                  ? "rgba(239,68,68,0.14)"
                  : item.kind === "success"
                    ? "rgba(34,197,94,0.14)"
                    : "rgba(56,189,248,0.14)",
            }}
          >
            {item.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

