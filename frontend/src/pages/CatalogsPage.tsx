/**
 * CatalogsPage - CRUD de catálogos maestros
 *
 * Gestiona entidades: parámetros, regiones, tecnologías, combustibles, emisiones, solvers.
 * Permite crear, editar y desactivar registros (desactivar requiere justificación si está en uso).
 *
 * Endpoints usados:
 * - catalogsApi.list(entity, excludeInactive)
 * - catalogsApi.create(), update(), deactivate()
 *
 * Solo usuarios con can_manage_catalogs pueden modificar; otros ven solo lectura.
 */
import { useEffect, useMemo, useState } from "react";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { useToast } from "@/app/providers/useToast";
import { catalogsApi } from "@/features/catalogs/api/catalogsApi";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { DataTable } from "@/shared/components/DataTable";
import { Modal } from "@/shared/components/Modal";
import { TextField } from "@/shared/components/TextField";
import type { CatalogEntity, CatalogItem } from "@/types/domain";

const entityTabs: CatalogEntity[] = ["parameter", "region", "technology", "fuel", "emission", "solver"];

const entityLabel: Record<CatalogEntity, string> = {
  parameter: "Parámetros",
  region: "Regiones",
  technology: "Tecnologías",
  fuel: "Combustibles",
  emission: "Emisiones",
  solver: "Solvers",
};

export function CatalogsPage() {
  const { user } = useCurrentUser();
  const { push } = useToast();
  const [entity, setEntity] = useState<CatalogEntity>("parameter");
  const [showInactive, setShowInactive] = useState(true);
  const [rows, setRows] = useState<CatalogItem[]>([]);
  const [loadingRows, setLoadingRows] = useState(false);
  const [editing, setEditing] = useState<CatalogItem | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", justification: "" });

  const canManage = Boolean(user?.can_manage_catalogs);

  async function loadRows(nextEntity = entity, nextShowInactive = showInactive) {
    setLoadingRows(true);
    try {
      const data = await catalogsApi.list(nextEntity, { includeInactive: nextShowInactive });
      setRows(data);
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo cargar el catálogo.", "error");
      setRows([]);
    } finally {
      setLoadingRows(false);
    }
  }

  // Recarga filas al cambiar entidad o visibilidad de inactivos
  useEffect(() => {
    void loadRows(entity, showInactive);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity, showInactive]);

  // Refresca al volver a la pestaña/ventana para reflejar cambios hechos en Escenarios.
  useEffect(() => {
    const handleFocus = () => {
      void loadRows(entity, showInactive);
    };
    const handleVisibility = () => {
      if (!document.hidden) {
        void loadRows(entity, showInactive);
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity, showInactive]);

  const title = useMemo(() => `Catálogo: ${entityLabel[entity]}`, [entity]);

  function openCreate() {
    setEditing(null);
    setForm({ name: "", justification: "" });
    setOpen(true);
  }

  function openEdit(item: CatalogItem) {
    setEditing(item);
    setForm({ name: item.name, justification: "" });
    setOpen(true);
  }

  /** Guarda (crear o actualizar) según si estamos editando; justificación obligatoria en update si en uso */
  async function save() {
    if (!canManage) return;
    try {
      if (editing) {
        const justification = form.justification.trim();
        await catalogsApi.update(entity, editing.id, {
          name: form.name.trim(),
          ...(justification ? { justification } : {}),
        });
      } else {
        await catalogsApi.create({
          entity,
          name: form.name.trim(),
        });
      }
      await loadRows(entity, showInactive);
      setOpen(false);
      push("Catálogo guardado.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo guardar.", "error");
    }
  }

  /** Desactiva un registro; pide justificación por prompt si está en uso */
  async function toggleActive(item: CatalogItem) {
    if (!canManage) return;
    const justification =
      window.prompt("Justificación (obligatoria si el registro ya está en uso):")?.trim() || undefined;
    await catalogsApi.deactivate(entity, item.id, justification);
    await loadRows(entity, showInactive);
    push("Registro desactivado.", "success");
  }

  return (
    <section className="pageSection" style={{ display: "grid", gap: 14 }}>
      <div className="toolbarRow">
        <div>
          <h1 style={{ margin: 0 }}>Catálogos</h1>
          <p style={{ margin: "6px 0 0", opacity: 0.75 }}>
            Vista completa del catálogo; puedes incluir o excluir registros inactivos.
          </p>
        </div>
        {canManage ? (
          <Button variant="primary" onClick={openCreate}>
            Nuevo registro
          </Button>
        ) : (
          <Badge variant="neutral">Solo lectura (sin permiso de administración)</Badge>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {entityTabs.map((tab) => (
          <Button key={tab} variant={tab === entity ? "primary" : "ghost"} onClick={() => setEntity(tab)}>
            {entityLabel[tab]}
          </Button>
        ))}
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
        Incluir desactivados
      </label>

      <DataTable
        rows={rows}
        rowKey={(r) => String(r.id)}
        columns={[
          { key: "id", header: "ID", render: (r) => r.id },
          { key: "name", header: "Nombre", render: (r) => r.name },
          {
            key: "active",
            header: "Estado",
            render: (r) => (
              <Badge variant={r.is_active ? "success" : "danger"}>{r.is_active ? "Activo" : "Inactivo"}</Badge>
            ),
          },
          {
            key: "actions",
            header: "Acciones",
            render: (r) =>
              canManage ? (
                <div style={{ display: "flex", gap: 8 }}>
                  <Button variant="ghost" onClick={() => openEdit(r)}>
                    Editar
                  </Button>
                  {r.is_active ? (
                    <Button variant="ghost" onClick={() => toggleActive(r)}>
                      Desactivar
                    </Button>
                  ) : null}
                </div>
              ) : (
                <span style={{ opacity: 0.7 }}>Solo lectura</span>
              ),
          },
        ]}
        searchableText={(r) => `${r.id} ${r.name}`}
      />
      {loadingRows ? <small style={{ opacity: 0.75 }}>Cargando catálogo...</small> : null}

      <Modal
        open={open}
        title={`${editing ? "Editar" : "Crear"} · ${title}`}
        onClose={() => setOpen(false)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={save} disabled={!canManage}>
              Guardar
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 10 }}>
          <TextField label="Nombre" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
          {editing ? (
            <TextField
              label="Justificación (si está en uso, es obligatoria)"
              value={form.justification}
              onChange={(e) => setForm((p) => ({ ...p, justification: e.target.value }))}
            />
          ) : null}
        </div>
      </Modal>
    </section>
  );
}

