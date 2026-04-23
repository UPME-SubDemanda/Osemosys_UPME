/**
 * Diálogo genérico de confirmación sí/no.
 *
 * Se usa para acciones reversibles con pequeña fricción intencional (quitar
 * etiqueta, desasignar permiso, etc.). Para acciones destructivas mayores
 * (eliminar escenario), prefiere un flujo explícito con tipeo de confirmación.
 */
import type { ReactNode } from "react";

import { Modal } from "@/shared/components/Modal";

type Props = {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  danger = false,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      footer={
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="btn btn--ghost" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? "btn btn--danger" : "btn btn--primary"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      }
    >
      <div style={{ fontSize: 14, lineHeight: 1.5 }}>{message}</div>
    </Modal>
  );
}
