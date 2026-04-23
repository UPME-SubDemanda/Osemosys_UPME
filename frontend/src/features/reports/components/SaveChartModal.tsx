/**
 * Modal para guardar una gráfica como plantilla reutilizable.
 *
 * Al abrirse, consulta las plantillas existentes del usuario para detectar si
 * ya hay una con exactamente la misma configuración (mismos filtros, unidad,
 * modo, etc.). En ese caso muestra una advertencia pero permite crear un
 * duplicado explícitamente.
 */
import { useEffect, useMemo, useState } from "react";
import { Modal } from "@/shared/components/Modal";
import { Button } from "@/shared/components/Button";
import { savedChartsApi } from "../api/savedChartsApi";
import type {
  SavedChartTemplate,
  SavedChartTemplateCreate,
} from "@/types/domain";
import type { ChartSelection } from "@/shared/charts/ChartSelector";

type Props = {
  open: boolean;
  onClose: () => void;
  selection: ChartSelection;
  compareMode: "off" | "facet";
  numScenarios: number;
  barOrientation: "vertical" | "horizontal";
  facetPlacement: "inline" | "stacked";
  facetLegendMode: "shared" | "perFacet";
  chartLabel?: string | null | undefined;
  onSaved?: (template: SavedChartTemplate) => void;
};

function buildDefaultName(params: {
  selection: ChartSelection;
  compareMode: "off" | "facet";
  numScenarios: number;
  chartLabel?: string | null | undefined;
}): string {
  const parts: string[] = [];
  parts.push(params.chartLabel?.trim() || params.selection.tipo);
  if (params.selection.sub_filtro) parts.push(`[${params.selection.sub_filtro}]`);
  if (params.selection.loc) parts.push(`(${params.selection.loc})`);
  parts.push(`· ${params.selection.un}`);
  if (params.selection.variable) parts.push(`· ${params.selection.variable}`);
  if (params.selection.agrupar_por) parts.push(`· ${params.selection.agrupar_por}`);
  parts.push(`· ${params.selection.viewMode ?? "column"}`);
  parts.push(
    params.compareMode === "facet"
      ? `· facet × ${params.numScenarios}`
      : `· 1 escenario`,
  );
  return parts.join(" ").slice(0, 240);
}

function buildDescription(params: {
  selection: ChartSelection;
  compareMode: "off" | "facet";
  numScenarios: number;
  barOrientation: "vertical" | "horizontal";
  facetPlacement: "inline" | "stacked";
  facetLegendMode: "shared" | "perFacet";
  chartLabel?: string | null | undefined;
}): string {
  const lines: string[] = [];
  lines.push(`Gráfica: ${params.chartLabel ?? params.selection.tipo}`);
  lines.push(`Variable: ${params.selection.variable || "—"}`);
  lines.push(`Unidad: ${params.selection.un}`);
  lines.push(`Sub-filtro: ${params.selection.sub_filtro || "—"}`);
  lines.push(`Localización: ${params.selection.loc || "—"}`);
  lines.push(`Agrupación: ${params.selection.agrupar_por || "—"}`);
  lines.push(`Tipo de trazo: ${params.selection.viewMode ?? "column"}`);
  lines.push(`Orientación de barras: ${params.barOrientation}`);
  lines.push(
    params.compareMode === "facet"
      ? `Modo: comparación por escenario (faceta) · ${params.numScenarios} escenarios · placement=${params.facetPlacement} · leyenda=${params.facetLegendMode}`
      : `Modo: un solo escenario`,
  );
  return lines.join("\n");
}

/** Firma canónica de una plantilla para detectar duplicados exactos. */
function signatureFromTemplate(t: SavedChartTemplate): string {
  return [
    t.tipo,
    t.un,
    t.sub_filtro ?? "",
    t.loc ?? "",
    t.variable ?? "",
    t.agrupar_por ?? "",
    t.view_mode ?? "",
    t.compare_mode,
    String(t.num_scenarios),
    t.bar_orientation ?? "",
    t.facet_placement ?? "",
    t.facet_legend_mode ?? "",
  ].join("|");
}

function signatureFromCandidate(params: {
  selection: ChartSelection;
  compareMode: "off" | "facet";
  numScenarios: number;
  barOrientation: "vertical" | "horizontal";
  facetPlacement: "inline" | "stacked";
  facetLegendMode: "shared" | "perFacet";
}): string {
  const { selection: s } = params;
  return [
    s.tipo,
    s.un,
    s.sub_filtro ?? "",
    s.loc ?? "",
    s.variable ?? "",
    s.agrupar_por ?? "",
    s.viewMode ?? "",
    params.compareMode,
    String(params.numScenarios),
    params.barOrientation,
    params.compareMode === "facet" ? params.facetPlacement : "",
    params.compareMode === "facet" ? params.facetLegendMode : "",
  ].join("|");
}

export function SaveChartModal({
  open,
  onClose,
  selection,
  compareMode,
  numScenarios,
  barOrientation,
  facetPlacement,
  facetLegendMode,
  chartLabel,
  onSaved,
}: Props) {
  const defaultName = useMemo(
    () =>
      buildDefaultName({ selection, compareMode, numScenarios, chartLabel }),
    [selection, compareMode, numScenarios, chartLabel],
  );
  const defaultDescription = useMemo(
    () =>
      buildDescription({
        selection,
        compareMode,
        numScenarios,
        barOrientation,
        facetPlacement,
        facetLegendMode,
        chartLabel,
      }),
    [
      selection,
      compareMode,
      numScenarios,
      barOrientation,
      facetPlacement,
      facetLegendMode,
      chartLabel,
    ],
  );

  const [name, setName] = useState(defaultName);
  const [description, setDescription] = useState(defaultDescription);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [existing, setExisting] = useState<SavedChartTemplate[]>([]);
  const [loadingExisting, setLoadingExisting] = useState(false);
  /** Usuario pidió crear duplicado explícitamente. */
  const [forceDuplicate, setForceDuplicate] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(defaultName);
    setDescription(defaultDescription);
    setError(null);
    setForceDuplicate(false);
    setLoadingExisting(true);
    savedChartsApi
      .list()
      .then((rows) => setExisting(rows))
      .catch((err) => {
        console.warn("No se pudieron cargar plantillas existentes", err);
        setExisting([]);
      })
      .finally(() => setLoadingExisting(false));
  }, [open, defaultName, defaultDescription]);

  const candidateSignature = useMemo(
    () =>
      signatureFromCandidate({
        selection,
        compareMode,
        numScenarios,
        barOrientation,
        facetPlacement,
        facetLegendMode,
      }),
    [
      selection,
      compareMode,
      numScenarios,
      barOrientation,
      facetPlacement,
      facetLegendMode,
    ],
  );

  const duplicates = useMemo(
    () =>
      existing.filter(
        (t) => signatureFromTemplate(t) === candidateSignature,
      ),
    [existing, candidateSignature],
  );

  const hasDuplicate = duplicates.length > 0;

  const handleSave = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("El nombre no puede estar vacío.");
      return;
    }
    if (hasDuplicate && !forceDuplicate) {
      setError(
        'Ya existe una gráfica con esta configuración. Confirma "Crear duplicado" para guardar igualmente.',
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload: SavedChartTemplateCreate = {
        name: trimmed,
        description: description.trim() || null,
        tipo: selection.tipo,
        un: selection.un,
        sub_filtro: selection.sub_filtro || null,
        loc: selection.loc || null,
        variable: selection.variable || null,
        agrupar_por: selection.agrupar_por || null,
        view_mode: selection.viewMode ?? null,
        compare_mode: compareMode,
        bar_orientation: barOrientation,
        facet_placement: compareMode === "facet" ? facetPlacement : null,
        facet_legend_mode: compareMode === "facet" ? facetLegendMode : null,
        num_scenarios: numScenarios,
        legend_title: null,
        filename_mode: compareMode === "facet" ? "result" : null,
      };
      const created = await savedChartsApi.create(payload);
      onSaved?.(created);
      onClose();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message?: string }).message ??
            "No se pudo guardar la gráfica."
          : "No se pudo guardar la gráfica.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Guardar gráfica para reportes">
      <div style={{ display: "grid", gap: 16 }}>
        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8" }}>
            Nombre de la gráfica
          </span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={255}
            style={{
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.12)",
              background: "rgba(15,23,42,0.7)",
              color: "#e2e8f0",
              fontSize: 14,
            }}
          />
          <span style={{ fontSize: 11, color: "#64748b" }}>
            Este nombre se usa en el listado y en el archivo generado.
          </span>
        </label>

        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8" }}>
            Descripción
          </span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={6}
            style={{
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.12)",
              background: "rgba(15,23,42,0.7)",
              color: "#e2e8f0",
              fontSize: 13,
              fontFamily: "inherit",
              resize: "vertical",
            }}
          />
        </label>

        <div
          style={{
            padding: 12,
            borderRadius: 8,
            background: "rgba(59,130,246,0.06)",
            border: "1px solid rgba(59,130,246,0.18)",
            fontSize: 12,
            color: "#93c5fd",
            lineHeight: 1.5,
          }}
        >
          <strong>Configuración capturada:</strong>
          <br />
          {compareMode === "facet"
            ? `Comparación por escenario · requiere ${numScenarios} escenarios al generar el reporte.`
            : "Un solo escenario · requiere 1 escenario al generar el reporte."}
        </div>

        {loadingExisting ? (
          <div style={{ fontSize: 12, color: "#64748b" }}>
            Buscando gráficas con la misma configuración…
          </div>
        ) : null}

        {hasDuplicate ? (
          <div
            style={{
              padding: 12,
              borderRadius: 8,
              background: "rgba(245,158,11,0.08)",
              border: "1px solid rgba(245,158,11,0.25)",
              color: "#fcd34d",
              fontSize: 12,
              lineHeight: 1.5,
              display: "grid",
              gap: 8,
            }}
          >
            <strong style={{ color: "#fde68a" }}>
              Esta gráfica ya existe con la misma configuración (
              {duplicates.length} coincidencia
              {duplicates.length === 1 ? "" : "s"}):
            </strong>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {duplicates.slice(0, 5).map((t) => {
                const ownerLabel = t.is_owner
                  ? "tuya"
                  : `de ${t.owner_username ?? "otro usuario"}`;
                const visibilityLabel = t.is_public ? "pública" : "privada";
                return (
                  <li key={t.id}>
                    <code style={{ fontSize: 11 }}>#{t.id}</code> {t.name}
                    <span style={{ opacity: 0.8 }}>
                      {" "}
                      · {ownerLabel} · {visibilityLabel}
                    </span>
                  </li>
                );
              })}
              {duplicates.length > 5 ? (
                <li style={{ opacity: 0.7 }}>… y {duplicates.length - 5} más</li>
              ) : null}
            </ul>
            <p style={{ margin: 0, fontSize: 12 }}>
              <strong>Recomendado:</strong> usa la existente (ya la puedes
              seleccionar en el Generador de reporte) y evita duplicados.
            </p>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                cursor: "pointer",
                borderTop: "1px solid rgba(245,158,11,0.2)",
                paddingTop: 8,
              }}
            >
              <input
                type="checkbox"
                checked={forceDuplicate}
                onChange={(e) => setForceDuplicate(e.target.checked)}
              />
              <span>Aun así, crear una nueva copia (con otro nombre)</span>
            </label>
          </div>
        ) : null}

        {error ? (
          <div
            style={{
              padding: 10,
              borderRadius: 8,
              background: "rgba(244,63,94,0.08)",
              border: "1px solid rgba(244,63,94,0.2)",
              color: "#fca5a5",
              fontSize: 13,
            }}
          >
            {error}
          </div>
        ) : null}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, flexWrap: "wrap" }}>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            {hasDuplicate && !forceDuplicate ? "Usar la existente" : "Cancelar"}
          </Button>
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={submitting || (hasDuplicate && !forceDuplicate)}
          >
            {submitting
              ? "Guardando…"
              : hasDuplicate
                ? forceDuplicate
                  ? "Crear copia nueva"
                  : "Ya existe — marca la casilla para duplicar"
                : "Guardar gráfica"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
