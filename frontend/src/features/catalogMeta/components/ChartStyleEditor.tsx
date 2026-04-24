/**
 * ChartStyleEditor — editor rápido de labels y colores para las series de
 * la gráfica actualmente desplegada. Se abre desde ResultDetailPage.
 *
 * Comportamiento:
 *  - Por cada serie con `code` editable: input de label + color.
 *  - Muestra advertencia con conteo de OTRAS gráficas afectadas al editar
 *    (via /catalog-meta/usage).
 *  - Al guardar, upsert labels (por code) y colors (por code + group inferido).
 *  - Tras guardar, llama invalidate-cache y cierra modal.
 */
import { useEffect, useMemo, useState } from "react";
import type { ChartSeries } from "@/types/domain";
import {
  catalogMetaApi,
  type ColorGroup,
} from "@/features/catalogMeta/api/catalogMetaApi";
import { Button } from "@/shared/components/Button";
import { Modal } from "@/shared/components/Modal";

type SeriesDraft = {
  code: string;
  label: string;
  color: string;
  original_label: string;
  original_color: string;
  usage_count: number;
  saving?: boolean;
  error?: string;
  dirty?: boolean;
};

function inferGroup(code: string): ColorGroup {
  if (code.startsWith("PWR")) return "pwr";
  if (code.startsWith("EMI")) return "emission";
  return "fuel";
}

export function ChartStyleEditor({
  open,
  onClose,
  series,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  series: ChartSeries[];
  onSaved?: () => void;
}) {
  const [drafts, setDrafts] = useState<SeriesDraft[]>([]);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [loadingUsage, setLoadingUsage] = useState(false);
  const [bulkSaving, setBulkSaving] = useState(false);

  const editableSeries = useMemo(
    () => series.filter((s) => !!s.code),
    [series],
  );

  useEffect(() => {
    if (!open) return;
    // Inicializar drafts.
    setDrafts(
      editableSeries.map((s) => ({
        code: s.code!,
        label: s.name,
        color: s.color,
        original_label: s.name,
        original_color: s.color,
        usage_count: 0,
      })),
    );
    setGlobalError(null);
    // Cargar conteos de uso.
    if (editableSeries.length === 0) return;
    let cancelled = false;
    setLoadingUsage(true);
    catalogMetaApi
      .codeUsage(editableSeries.map((s) => s.code!))
      .then((resp) => {
        if (cancelled) return;
        setDrafts((prev) =>
          prev.map((d) => ({
            ...d,
            usage_count: resp.items[d.code]?.count ?? 0,
          })),
        );
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingUsage(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, editableSeries]);

  const updateDraft = (code: string, patch: Partial<SeriesDraft>) =>
    setDrafts((prev) =>
      prev.map((d) =>
        d.code === code
          ? {
              ...d,
              ...patch,
              dirty:
                (patch.label ?? d.label) !== d.original_label ||
                (patch.color ?? d.color).toLowerCase() !== d.original_color.toLowerCase(),
            }
          : d,
      ),
    );

  const dirtyDrafts = drafts.filter((d) => d.dirty);

  const totalAffectedCharts = useMemo(() => {
    const set = new Set<number>();
    for (const d of dirtyDrafts) {
      if (d.usage_count > 0) set.add(d.usage_count);
    }
    // Union approximation: max single usage + count drafts
    return dirtyDrafts.reduce((acc, d) => acc + d.usage_count, 0);
  }, [dirtyDrafts]);

  const saveAll = async () => {
    if (dirtyDrafts.length === 0) {
      onClose();
      return;
    }
    setBulkSaving(true);
    setGlobalError(null);
    const errors: string[] = [];
    for (const d of dirtyDrafts) {
      try {
        // Label upsert.
        if (d.label !== d.original_label) {
          await catalogMetaApi.upsertLabel({
            code: d.code,
            label_es: d.label,
            category: "technology",
          });
        }
        // Color upsert (intenta con grupo inferido).
        if (d.color.toLowerCase() !== d.original_color.toLowerCase()) {
          await catalogMetaApi.upsertColor({
            key: d.code,
            group: inferGroup(d.code),
            color_hex: d.color.toLowerCase(),
          });
        }
      } catch (e) {
        errors.push(`${d.code}: ${e instanceof Error ? e.message : "error"}`);
      }
    }
    setBulkSaving(false);
    if (errors.length > 0) {
      setGlobalError(errors.join(" · "));
      return;
    }
    // Invalidar cache global.
    await catalogMetaApi.invalidateCache().catch(() => {});
    onSaved?.();
    onClose();
  };

  return (
    <Modal open={open} onClose={onClose} title="Editar labels y colores de esta gráfica" wide>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {editableSeries.length === 0 ? (
          <p style={{ fontSize: 13, opacity: 0.7 }}>
            Esta gráfica no expone códigos editables por serie (p.ej. comparación por
            escenario). Edita desde la pestaña admin de visualización.
          </p>
        ) : (
          <>
            <p style={{ margin: 0, fontSize: 12, opacity: 0.75 }}>
              Los cambios son <b>globales</b>: afectan a todas las gráficas que usen
              cada código. La columna "Afecta" estima cuántas gráficas más rendearán
              el cambio.
            </p>
            <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead style={{ background: "rgba(255,255,255,0.03)" }}>
                  <tr>
                    <Th style={{ width: 180 }}>Código</Th>
                    <Th>Label</Th>
                    <Th style={{ width: 130 }}>Color</Th>
                    <Th style={{ width: 80, textAlign: "right" }}>Afecta</Th>
                  </tr>
                </thead>
                <tbody>
                  {drafts.map((d) => {
                    const warn = d.dirty && d.usage_count > 0;
                    return (
                      <tr
                        key={d.code}
                        style={{
                          borderTop: "1px solid rgba(255,255,255,0.06)",
                          background: d.dirty ? "rgba(80,140,255,0.06)" : undefined,
                        }}
                      >
                        <Td>
                          <code style={{ fontSize: 11 }}>{d.code}</code>
                        </Td>
                        <Td>
                          <input
                            type="text"
                            value={d.label}
                            onChange={(e) => updateDraft(d.code, { label: e.target.value })}
                            style={{ ...fieldStyle, width: "100%" }}
                          />
                        </Td>
                        <Td>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                            <input
                              type="color"
                              value={d.color.length === 7 ? d.color : d.color.slice(0, 7)}
                              onChange={(e) => updateDraft(d.code, { color: e.target.value.toLowerCase() })}
                              style={{
                                width: 24,
                                height: 22,
                                padding: 0,
                                border: "1px solid rgba(255,255,255,0.12)",
                                background: "transparent",
                                cursor: "pointer",
                              }}
                            />
                            <code style={{ fontSize: 11 }}>{d.color}</code>
                          </span>
                        </Td>
                        <Td style={{ textAlign: "right" }}>
                          <span
                            style={{
                              fontSize: 11,
                              padding: "2px 6px",
                              borderRadius: 999,
                              background: warn
                                ? "rgba(255,180,70,0.15)"
                                : "rgba(255,255,255,0.05)",
                              color: warn ? "rgba(255,200,120,0.95)" : "var(--muted)",
                              border: `1px solid ${warn ? "rgba(255,180,70,0.4)" : "rgba(255,255,255,0.1)"}`,
                            }}
                            title={warn ? "Otras gráficas afectadas por este código" : "Sin impacto en otras gráficas"}
                          >
                            {loadingUsage ? "…" : `${d.usage_count} más`}
                          </span>
                        </Td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {dirtyDrafts.length > 0 ? (
              <div
                role="alert"
                style={{
                  fontSize: 13,
                  padding: "8px 12px",
                  background: "rgba(255,180,70,0.08)",
                  border: "1px solid rgba(255,180,70,0.3)",
                  borderRadius: 6,
                  color: "rgba(255,210,150,0.95)",
                }}
              >
                ⚠ Estás editando <b>{dirtyDrafts.length}</b> {dirtyDrafts.length === 1 ? "serie" : "series"}.
                Estos cambios afectan aproximadamente a <b>{totalAffectedCharts}</b> instancias
                de uso en otras gráficas del catálogo. Son cambios globales: todas las
                gráficas del sistema usarán el nuevo label/color para esos códigos.
              </div>
            ) : null}

            {globalError ? (
              <div
                role="alert"
                style={{
                  fontSize: 13,
                  padding: "8px 12px",
                  background: "rgba(255,90,90,0.08)",
                  border: "1px solid rgba(255,90,90,0.3)",
                  borderRadius: 6,
                  color: "rgba(255,180,180,0.95)",
                }}
              >
                {globalError}
              </div>
            ) : null}
          </>
        )}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 6 }}>
          <Button variant="ghost" onClick={onClose} disabled={bulkSaving}>
            Cancelar
          </Button>
          <Button onClick={saveAll} disabled={bulkSaving || dirtyDrafts.length === 0}>
            {bulkSaving ? "Guardando…" : `Guardar (${dirtyDrafts.length})`}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th
      style={{
        textAlign: "left",
        fontSize: 12,
        padding: "8px 10px",
        color: "var(--muted)",
        fontWeight: 500,
        ...style,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <td style={{ padding: "6px 10px", fontSize: 13, ...style }}>{children}</td>;
}

const fieldStyle: React.CSSProperties = {
  background: "transparent",
  color: "inherit",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 4,
  padding: "4px 8px",
  fontSize: 13,
};
