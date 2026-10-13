import { useCallback, useEffect, useState } from "react";

import { useToast } from "@/app/providers/useToast";
import type { MosekLicenseStatus } from "@/features/systemSettings/api/mosekLicenseApi";
import { Button } from "@/shared/components/Button";
import { Card } from "@/shared/components/Card";

type Props = {
  title: string;
  description: string;
  canEdit: boolean;
  load: () => Promise<MosekLicenseStatus>;
  upload: (file: File) => Promise<MosekLicenseStatus>;
  remove: () => Promise<MosekLicenseStatus>;
};

export function MosekLicenseControl({
  title,
  description,
  canEdit,
  load,
  upload,
  remove,
}: Props) {
  const { push } = useToast();
  const [license, setLicense] = useState<MosekLicenseStatus | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setLicense(await load());
    } catch (error) {
      push(error instanceof Error ? error.message : "No se pudo consultar la licencia.", "error");
    } finally {
      setLoading(false);
    }
  }, [load, push]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function save() {
    if (!file || !canEdit) return;
    setSaving(true);
    try {
      setLicense(await upload(file));
      setFile(null);
      push("Licencia MOSEK guardada cifrada.", "success");
    } catch (error) {
      push(error instanceof Error ? error.message : "No se pudo guardar la licencia.", "error");
    } finally {
      setSaving(false);
    }
  }

  async function clear() {
    if (!canEdit) return;
    setSaving(true);
    try {
      setLicense(await remove());
      setFile(null);
      push("Licencia MOSEK eliminada.", "success");
    } catch (error) {
      push(error instanceof Error ? error.message : "No se pudo eliminar la licencia.", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <div style={{ padding: 16, display: "grid", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <p className="muted" style={{ margin: "6px 0 0", maxWidth: 760 }}>{description}</p>
        </div>
        {loading ? <div className="muted">Consultando estado de la licencia…</div> : (
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <strong role="status">
              {license?.configured ? "Licencia configurada" : "Sin licencia configurada"}
            </strong>
            {license?.configured && license.updated_at ? (
              <span className="muted">Actualizada {new Date(license.updated_at).toLocaleString()}</span>
            ) : null}
          </div>
        )}
        {!canEdit ? <p className="muted" style={{ margin: 0 }}>Solo lectura.</p> : (
          <>
            <label className="field" style={{ margin: 0, maxWidth: 520 }}>
              <span className="field__label">Archivo de licencia MOSEK (.lic)</span>
              <input
                className="field__input"
                type="file"
                accept=".lic,text/plain"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                disabled={saving}
              />
            </label>
            {file ? <span className="muted">Seleccionado: {file.name}</span> : null}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button onClick={() => void save()} disabled={!file || saving}>
                {saving ? "Guardando…" : "Guardar licencia"}
              </Button>
              {license?.configured ? (
                <Button variant="ghost" onClick={() => void clear()} disabled={saving}>
                  Eliminar licencia
                </Button>
              ) : null}
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
