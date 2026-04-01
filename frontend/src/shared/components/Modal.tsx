/**
 * Modal/diálogo con soporte de tecla Escape para cerrar y auto-focus en el contenedor.
 * El overlay cierra al hacer clic fuera (salvo si disableBackdropClose=true).
 */
import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  /** Si true, el modal solo se cierra con el botón Cerrar (no con clic afuera ni Escape). */
  disableBackdropClose?: boolean;
};

export function Modal({ open, title, onClose, children, footer, wide = false, disableBackdropClose }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || disableBackdropClose) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose, disableBackdropClose]);

  useEffect(() => {
    if (open) {
      dialogRef.current?.focus();
    }
  }, [open]);

  if (!open) return null;

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
      onClick={disableBackdropClose ? undefined : onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        zIndex: 200,
        outline: "none",
        overflowY: "auto",
      }}
    >
      {/* Evita que el clic en el contenido cierre el modal */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: wide ? "min(1100px,100%)" : "min(680px,100%)",
          background: "rgba(11,18,32,0.98)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 14,
          boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
          maxHeight: wide ? "min(90vh, calc(100vh - 32px))" : "min(760px, calc(100vh - 32px))",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <header
          style={{
            padding: 16,
            borderBottom: "1px solid rgba(255,255,255,0.08)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            flexShrink: 0,
          }}
        >
          <h3 style={{ margin: 0 }}>{title}</h3>
          <button className="btn btn--ghost" onClick={onClose} type="button">
            Cerrar
          </button>
        </header>
        <div
          style={{
            padding: 16,
            overflowY: "auto",
            minHeight: 0,
          }}
        >
          {children}
        </div>
        {footer ? (
          <footer
            style={{
              padding: 16,
              borderTop: "1px solid rgba(255,255,255,0.08)",
              flexShrink: 0,
              background: "rgba(11,18,32,0.98)",
            }}
          >
            {footer}
          </footer>
        ) : null}
      </div>
    </div>
  );
}
