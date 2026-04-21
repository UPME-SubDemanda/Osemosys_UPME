/**
 * ScenariosPage - Lista y gestión de escenarios energéticos.
 *
 * Usa paginación y filtros server-side para evitar perder escenarios fuera de la
 * primera página y para soportar visibilidad global según la política acordada.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { useToast } from "@/app/providers/useToast";
import { officialImportApi } from "@/features/officialImport/api/officialImportApi";
import {
  scenariosApi,
  type SandExportVerification,
  type SandIntegrationSummary,
} from "@/features/scenarios/api/scenariosApi";
import { isApiError } from "@/shared/errors/ApiError";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Modal } from "@/shared/components/Modal";
import { TextField } from "@/shared/components/TextField";
import { SandExportVerificationPanel } from "@/shared/components/SandExportVerificationPanel";
import { UploadProgress, type UploadPhase } from "@/shared/components/UploadProgress";
import { paths } from "@/routes/paths";
import { ScenarioTagChip } from "@/shared/components/ScenarioTagChip";
import type { Scenario, ScenarioEditPolicy, ScenarioOperationJob, ScenarioTag, SimulationType } from "@/types/domain";

const editPolicyHelp: Record<ScenarioEditPolicy, string> = {
  OWNER_ONLY: "Solo el propietario administra permisos y edición.",
  OPEN: "Todos con acceso pueden editar directamente.",
  RESTRICTED: "Visible en lectura; solo permisos explícitos editan.",
};

const editPolicyLabel: Record<ScenarioEditPolicy, string> = {
  OWNER_ONLY: "Solo propietario",
  OPEN: "Abierta",
  RESTRICTED: "Restringida",
};

const simulationTypeLabel: Record<SimulationType, string> = {
  NATIONAL: "Nacional",
  REGIONAL: "Regional",
};

/** Misma regla que editar metadatos del escenario (propietario o edición directa explícita). */
function canAssignScenarioTag(row: Scenario): boolean {
  const a = row.effective_access;
  if (!a) return false;
  return Boolean(a.is_owner || a.can_edit_direct);
}

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

/** Colores predefinidos para etiquetas (legibles con texto blanco en el chip). */
const SCENARIO_TAG_COLOR_PALETTE = [
  "#3B82F6",
  "#2563EB",
  "#0EA5E9",
  "#06B6D4",
  "#14B8A6",
  "#22C55E",
  "#65A30D",
  "#EAB308",
  "#F59E0B",
  "#EA580C",
  "#DC2626",
  "#EC4899",
  "#A855F7",
  "#7C3AED",
  "#6366F1",
  "#64748B",
] as const;

function normalizeTagHex(value: string): string {
  const v = value.trim();
  if (/^#[0-9A-Fa-f]{6}$/.test(v)) return v.toUpperCase();
  return v;
}

const SAND_CONFLICT_KEY_DIMS = [
  "Parameter",
  "REGION",
  "TECHNOLOGY",
  "EMISSION",
  "MODE_OF_OPERATION",
  "FUEL",
  "TIMESLICE",
  "STORAGE",
  "REGION2",
] as const;

function formatArchivosValores(archivos: unknown): string {
  if (!archivos || typeof archivos !== "object" || Array.isArray(archivos)) {
    return String(archivos ?? "");
  }
  const lines: string[] = [];
  for (const [nombre, val] of Object.entries(archivos as Record<string, unknown>)) {
    if (val !== null && typeof val === "object" && !Array.isArray(val)) {
      lines.push(`  • ${nombre}:\n${JSON.stringify(val, null, 2).split("\n").map((l) => `    ${l}`).join("\n")}`);
    } else {
      lines.push(`  • ${nombre}: ${String(val)}`);
    }
  }
  return lines.join("\n");
}

/** Texto legible para el panel «Ver más»: conflictos entre archivos nuevos (cabecera API). */
function formatSandConflictsDetail(
  conflictos: Record<string, unknown>[] | undefined,
  conflictosCount: number,
): string {
  if (!conflictosCount) {
    return "No hubo conflictos entre archivos nuevos.";
  }
  if (!conflictos?.length) {
    return `Se indicaron ${conflictosCount} conflicto(s), pero el detalle no vino en el resumen. Revisa el Excel «Conflictos» en cambios_integracion.xlsx si lo descargaste.`;
  }
  const blocks = conflictos.map((raw, idx) => {
    const o = raw;
    const tipo = o.tipo === "MODIFICADA" ? "Celda modificada en disputa" : o.tipo === "NUEVA" ? "Fila nueva en disputa" : String(o.tipo ?? "?");
    const dims = SAND_CONFLICT_KEY_DIMS.map((k) => {
      const v = o[k];
      if (v === undefined || v === null || v === "") return null;
      return `${k}: ${String(v)}`;
    })
      .filter((x): x is string => Boolean(x))
      .join(" · ");
    const columna = o.columna !== undefined && o.columna !== null && o.columna !== "" ? `Columna / ámbito: ${String(o.columna)}` : "";
    const arch = formatArchivosValores(o.archivos);
    return [`${idx + 1}. ${tipo}`, dims, columna, arch ? `Valores propuestos por archivo:\n${arch}` : ""]
      .filter((line) => line.length > 0)
      .join("\n");
  });
  return blocks.join("\n\n—\n\n");
}

function formatSandIntegrationFailureDetail(summary: SandIntegrationSummary): string {
  const parts: string[] = [];
  if (summary.resumen?.trim()) {
    parts.push(`--- Resumen ---\n${summary.resumen.trim()}`);
  }
  if (summary.errors?.length) {
    parts.push(
      `--- Errores ---\n${summary.errors.map((line, i) => `${i + 1}. ${line}`).join("\n")}`,
    );
  }
  if (summary.warnings?.length) {
    parts.push(`--- Advertencias ---\n${summary.warnings.join("\n")}`);
  }
  if (summary.conflictos_count > 0) {
    parts.push(
      `--- Conflictos entre archivos nuevos ---\n${formatSandConflictsDetail(summary.conflictos, summary.conflictos_count)}`,
    );
  }
  return parts.join("\n\n") || "La integración falló sin mensaje adicional.";
}

function formatConcatAxiosErrorDetail(err: unknown): string {
  if (isApiError(err)) {
    let s = err.message;
    const details = err.details as { response?: unknown } | undefined;
    if (details?.response !== undefined && details.response !== null) {
      const r = details.response;
      if (typeof r === "object") {
        s += `\n\n--- Detalle del servidor ---\n${JSON.stringify(r, null, 2)}`;
      } else if (typeof r === "string") {
        s += `\n\n--- Detalle ---\n${r}`;
      }
    }
    return s;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

function buildCloneName(sourceName: string): string {
  const normalized = sourceName.trim().replace(/(?:\s*\(copia\))+$/i, "").trim();
  return `${normalized || sourceName.trim()} (copia)`;
}

export function ScenariosPage() {
  const navigate = useNavigate();
  const { push } = useToast();
  const { user } = useCurrentUser();
  const [rows, setRows] = useState<Scenario[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(25);
  const [loadingRows, setLoadingRows] = useState(false);
  const [search, setSearch] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("");
  const [policyFilter, setPolicyFilter] = useState<ScenarioEditPolicy | "ALL">("ALL");

  const [openCreate, setOpenCreate] = useState(false);
  const [openExcel, setOpenExcel] = useState(false);
  const [openCsv, setOpenCsv] = useState(false);
  const [openConcatSand, setOpenConcatSand] = useState(false);
  const [openVerifySand, setOpenVerifySand] = useState(false);
  const [verifyBaseFile, setVerifyBaseFile] = useState<File | null>(null);
  const [verifyNewFiles, setVerifyNewFiles] = useState<File[]>([]);
  const [verifyIntegratedFile, setVerifyIntegratedFile] = useState<File | null>(null);
  const [verifyDropTechs, setVerifyDropTechs] = useState("");
  const [verifyDropFuels, setVerifyDropFuels] = useState("");
  const [verifyUploadPhase, setVerifyUploadPhase] = useState<UploadPhase>("idle");
  const [verifyUploadPercent, setVerifyUploadPercent] = useState(0);
  const [verifyUploadStartedAt, setVerifyUploadStartedAt] = useState<number | null>(null);
  const [verifyResult, setVerifyResult] = useState<SandExportVerification | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editPolicy, setEditPolicy] = useState<ScenarioEditPolicy>("OWNER_ONLY");
  const [simulationType, setSimulationType] = useState<SimulationType>("NATIONAL");
  const [saving, setSaving] = useState(false);

  const [openClone, setOpenClone] = useState(false);
  const [cloneSourceId, setCloneSourceId] = useState<number | null>(null);
  const [cloneName, setCloneName] = useState("");
  const [cloneEditPolicy, setCloneEditPolicy] = useState<ScenarioEditPolicy>("OWNER_ONLY");
  const [cloning, setCloning] = useState(false);
  const [cloneJobs, setCloneJobs] = useState<ScenarioOperationJob[]>([]);
  const [downloadingScenarioId, setDownloadingScenarioId] = useState<number | null>(null);
  const [tagModalScenario, setTagModalScenario] = useState<Scenario | null>(null);
  const [tagModalSelection, setTagModalSelection] = useState("");
  const [tagModalSaving, setTagModalSaving] = useState(false);

  const [scenarioTags, setScenarioTags] = useState<ScenarioTag[]>([]);
  const [tagSelectCreate, setTagSelectCreate] = useState("");
  const [tagSelectExcel, setTagSelectExcel] = useState("");
  const [includeUdcExcel, setIncludeUdcExcel] = useState(false);
  const [openTagsCatalog, setOpenTagsCatalog] = useState(false);
  const [tagCatName, setTagCatName] = useState("");
  const [tagCatColor, setTagCatColor] = useState("#3B82F6");
  const [tagCatSort, setTagCatSort] = useState("0");
  const [savingCatalogTag, setSavingCatalogTag] = useState(false);

  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [excelSheets, setExcelSheets] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [loadingSheets, setLoadingSheets] = useState(false);
  const [importing, setImporting] = useState(false);
  const [csvImporting, setCsvImporting] = useState(false);
  const [excelUploadPhase, setExcelUploadPhase] = useState<UploadPhase>("idle");
  const [excelUploadPercent, setExcelUploadPercent] = useState(0);
  const [excelUploadStartedAt, setExcelUploadStartedAt] = useState<number | null>(null);
  const importAbortRef = useRef<AbortController | null>(null);
  const createdScenarioIdRef = useRef<number | null>(null);
  const concatAbortRef = useRef<AbortController | null>(null);
  const verifyAbortRef = useRef<AbortController | null>(null);
  const [concatBaseFile, setConcatBaseFile] = useState<File | null>(null);
  const [concatNewFiles, setConcatNewFiles] = useState<File[]>([]);
  const [concatDropTechs, setConcatDropTechs] = useState("");
  const [concatDropFuels, setConcatDropFuels] = useState("");
  const [concatIncludeLogTxt, setConcatIncludeLogTxt] = useState(false);
  const [concatingSand, setConcatingSand] = useState(false);
  const [concatUploadPhase, setConcatUploadPhase] = useState<UploadPhase>("idle");
  const [concatUploadPercent, setConcatUploadPercent] = useState(0);
  const [concatUploadStartedAt, setConcatUploadStartedAt] = useState<number | null>(null);
  const [concatErrorDetail, setConcatErrorDetail] = useState<string | null>(null);
  const [concatErrorExpanded, setConcatErrorExpanded] = useState(false);
  const [concatDoneConflictsDetail, setConcatDoneConflictsDetail] = useState<string | null>(null);
  const [concatDoneConflictsExpanded, setConcatDoneConflictsExpanded] = useState(false);
  const [concatDoneConflictCount, setConcatDoneConflictCount] = useState(0);
  const [concatExportVerification, setConcatExportVerification] = useState<SandExportVerification | null>(null);

  const fetchScenarios = useCallback(async () => {
    if (!user) return;
    setLoadingRows(true);
    try {
      const res = await scenariosApi.listScenarios({
        ...(search.trim() ? { busqueda: search.trim() } : {}),
        ...(ownerFilter.trim() ? { owner: ownerFilter.trim() } : {}),
        ...(policyFilter === "ALL" ? {} : { edit_policy: policyFilter }),
        cantidad: pageSize,
        offset: page,
      });
      setRows(res.data);
      setTotal(res.meta.total);
    } catch (error) {
      push(error instanceof Error ? error.message : "No se pudo cargar el listado de escenarios.", "error");
    } finally {
      setLoadingRows(false);
    }
  }, [ownerFilter, page, pageSize, policyFilter, push, search, user]);

  const loadScenarioTags = useCallback(async () => {
    if (!user) return;
    try {
      const data = await scenariosApi.listScenarioTags();
      setScenarioTags(data);
    } catch {
      setScenarioTags([]);
    }
  }, [user]);

  useEffect(() => {
    void fetchScenarios();
  }, [fetchScenarios]);

  useEffect(() => {
    void loadScenarioTags();
  }, [loadScenarioTags]);

  const refreshCloneJobs = useCallback(async () => {
    if (!user) return;
    try {
      const res = await scenariosApi.listScenarioOperations({
        operation_type: "CLONE_SCENARIO",
        cantidad: 50,
        offset: 1,
      });
      setCloneJobs(res.data);
    } catch {
      // Sin ruido en UI: es un dato auxiliar de monitoreo.
    }
  }, [user]);

  useEffect(() => {
    void refreshCloneJobs();
  }, [refreshCloneJobs]);

  useEffect(() => {
    const hasActive = cloneJobs.some((j) => j.status === "QUEUED" || j.status === "RUNNING");
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      void Promise.all([refreshCloneJobs(), fetchScenarios()]);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [cloneJobs, fetchScenarios, refreshCloneJobs]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function resetCloneModal() {
    setOpenClone(false);
    setCloneSourceId(null);
    setCloneName("");
    setCloneEditPolicy("OWNER_ONLY");
  }

  async function handleCreate() {
    if (!user) return;
    if (!name.trim()) {
      push("El nombre del escenario es obligatorio.", "error");
      return;
    }
    setSaving(true);
    try {
      await scenariosApi.createScenario({
        name: name.trim(),
        description: description.trim(),
        edit_policy: editPolicy,
        simulation_type: simulationType,
        ...(tagSelectCreate ? { tag_id: Number(tagSelectCreate) } : {}),
      });
      setOpenCreate(false);
      setName("");
      setDescription("");
      setEditPolicy("OWNER_ONLY");
      setSimulationType("NATIONAL");
      setTagSelectCreate("");
      setPage(1);
      await fetchScenarios();
      push("Escenario creado correctamente.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo crear el escenario.", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleClone() {
    if (!cloneSourceId || !cloneName.trim()) {
      push("El nombre del escenario es obligatorio.", "error");
      return;
    }
    setCloning(true);
    // Se cierra inmediatamente para que el usuario vea progreso en la tabla.
    resetCloneModal();
    try {
      const job = await scenariosApi.cloneScenarioAsync(cloneSourceId, {
        name: cloneName.trim(),
        edit_policy: cloneEditPolicy,
      });
      setCloneJobs((prev) => [job, ...prev]);
      void Promise.all([refreshCloneJobs(), fetchScenarios()]);
      push("Copia iniciada. Puedes seguir el progreso en la tabla.", "info");
    } catch (err) {
      resetCloneModal();
      push(err instanceof Error ? err.message : "No se pudo copiar el escenario.", "error");
    } finally {
      setCloning(false);
    }
  }

  async function loadSheets() {
    if (!excelFile) return;
    setLoadingSheets(true);
    try {
      const res = await officialImportApi.listWorkbookSheets(excelFile);
      setExcelSheets(res.sheets);
      setSelectedSheet(res.sheets[0] ?? "");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudieron leer las hojas del Excel.", "error");
      setExcelSheets([]);
      setSelectedSheet("");
    } finally {
      setLoadingSheets(false);
    }
  }

  async function handleCreateFromExcel() {
    if (!user) return;
    if (!excelFile) {
      push("Selecciona un archivo Excel.", "error");
      return;
    }
    if (!selectedSheet) {
      push("Selecciona una hoja.", "error");
      return;
    }
    if (!name.trim()) {
      push("El nombre del escenario es obligatorio.", "error");
      return;
    }
    const abortCtrl = new AbortController();
    importAbortRef.current = abortCtrl;
    createdScenarioIdRef.current = null;
    setImporting(true);
    setExcelUploadPhase("uploading");
    setExcelUploadPercent(0);
    setExcelUploadStartedAt(Date.now());
    try {
      const res = await scenariosApi.createScenarioFromExcel(
        {
          file: excelFile,
          sheet_name: selectedSheet,
          scenario_name: name.trim(),
          description: description.trim(),
          edit_policy: editPolicy,
          simulation_type: simulationType,
          include_udc_reserve_margin: includeUdcExcel,
          ...(tagSelectExcel ? { tag_id: Number(tagSelectExcel) } : {}),
        },
        (percent) => {
          setExcelUploadPercent(percent);
          if (percent >= 100) setExcelUploadPhase("processing");
        },
        () => setExcelUploadPhase("processing"),
        abortCtrl.signal,
      );
      createdScenarioIdRef.current = res.scenario.id;
      setExcelUploadPhase("done");
      push("Escenario creado e importado correctamente.", "success");
      setTimeout(() => {
        setOpenExcel(false);
        resetExcelModal();
        void fetchScenarios();
        navigate(paths.scenarioDetail(res.scenario.id));
      }, 1200);
    } catch (err) {
      if (abortCtrl.signal.aborted) return;
      setExcelUploadPhase("error");
      push(err instanceof Error ? err.message : "No se pudo crear/importar el escenario.", "error");
    } finally {
      setImporting(false);
      importAbortRef.current = null;
    }
  }

  async function handleCreateFromCsv() {
    if (!user) return;
    if (!csvFile) {
      push("Selecciona un ZIP con CSV.", "error");
      return;
    }
    if (!name.trim()) {
      push("El nombre del escenario es obligatorio.", "error");
      return;
    }
    setCsvImporting(true);
    try {
      const scenario = await scenariosApi.createScenarioFromCsv({
        file: csvFile,
        scenario_name: name.trim(),
        description: description.trim(),
        edit_policy: editPolicy,
        simulation_type: simulationType,
        ...(tagSelectExcel ? { tag_id: Number(tagSelectExcel) } : {}),
      });
      push("Escenario creado desde CSV correctamente.", "success");
      setOpenCsv(false);
      resetCsvModal();
      await fetchScenarios();
      navigate(paths.scenarioDetail(scenario.id));
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo crear/importar el escenario desde CSV.", "error");
    } finally {
      setCsvImporting(false);
    }
  }

  function resetExcelModal() {
    setExcelFile(null);
    setExcelSheets([]);
    setSelectedSheet("");
    setName("");
    setDescription("");
    setEditPolicy("OWNER_ONLY");
    setSimulationType("NATIONAL");
    setTagSelectExcel("");
    setIncludeUdcExcel(false);
    setExcelUploadPhase("idle");
    setExcelUploadPercent(0);
    setExcelUploadStartedAt(null);
    createdScenarioIdRef.current = null;
  }

  function resetCsvModal() {
    setCsvFile(null);
    setName("");
    setDescription("");
    setEditPolicy("OWNER_ONLY");
    setSimulationType("NATIONAL");
    setTagSelectExcel("");
  }

  async function handleAddCatalogTag() {
    if (!tagCatName.trim()) {
      push("El nombre de la etiqueta es obligatorio.", "error");
      return;
    }
    const hex = normalizeTagHex(tagCatColor);
    if (!/^#[0-9A-Fa-f]{6}$/.test(hex)) {
      push("Elige un color.", "error");
      return;
    }
    setSavingCatalogTag(true);
    try {
      await scenariosApi.createScenarioTag({
        name: tagCatName.trim(),
        color: hex,
        sort_order: Number(tagCatSort) || 0,
      });
      setTagCatName("");
      setTagCatColor("#3B82F6");
      setTagCatSort("0");
      await loadScenarioTags();
      void fetchScenarios();
      push("Etiqueta creada.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo crear la etiqueta.", "error");
    } finally {
      setSavingCatalogTag(false);
    }
  }

  async function handleDeleteCatalogTag(tagId: number) {
    if (!window.confirm("¿Eliminar esta etiqueta? Los escenarios asociados quedarán sin etiqueta.")) return;
    try {
      await scenariosApi.deleteScenarioTag(tagId);
      await loadScenarioTags();
      void fetchScenarios();
      if (tagSelectCreate === String(tagId)) setTagSelectCreate("");
      if (tagSelectExcel === String(tagId)) setTagSelectExcel("");
      push("Etiqueta eliminada.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo eliminar la etiqueta.", "error");
    }
  }

  function openScenarioTagModal(row: Scenario) {
    setTagModalScenario(row);
    setTagModalSelection(row.tag ? String(row.tag.id) : "");
  }

  function closeScenarioTagModal() {
    setTagModalScenario(null);
    setTagModalSelection("");
    setTagModalSaving(false);
  }

  async function saveScenarioTagModal() {
    if (!tagModalScenario) return;
    if (!scenarioTags.length && tagModalSelection !== "") {
      push("No hay etiquetas en el catálogo.", "error");
      return;
    }
    const nextId = tagModalSelection === "" ? null : Number(tagModalSelection);
    const currentId = tagModalScenario.tag?.id ?? null;
    if (nextId === currentId) {
      closeScenarioTagModal();
      return;
    }
    setTagModalSaving(true);
    try {
      await scenariosApi.updateScenario(tagModalScenario.id, { tag_id: nextId });
      await fetchScenarios();
      push(nextId === null ? "Etiqueta quitada." : "Etiqueta actualizada.", "success");
      closeScenarioTagModal();
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo guardar la etiqueta.", "error");
    } finally {
      setTagModalSaving(false);
    }
  }

  async function removeScenarioTagFromModal() {
    if (!tagModalScenario) return;
    setTagModalSaving(true);
    try {
      await scenariosApi.updateScenario(tagModalScenario.id, { tag_id: null });
      await fetchScenarios();
      push("Etiqueta quitada.", "success");
      closeScenarioTagModal();
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo quitar la etiqueta.", "error");
    } finally {
      setTagModalSaving(false);
    }
  }

  async function handleDownloadExcel(row: Scenario) {
    setDownloadingScenarioId(row.id);
    try {
      const { blob, filename } = await scenariosApi.downloadScenarioExcel(row.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      push("Descarga iniciada.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo descargar el Excel.", "error");
    } finally {
      setDownloadingScenarioId(null);
    }
  }

  async function handleCloseExcel() {
    if (importing) {
      importAbortRef.current?.abort();
      importAbortRef.current = null;
      setImporting(false);
    }
    const partialId = createdScenarioIdRef.current;
    if (partialId) {
      try {
        await scenariosApi.deleteScenario(partialId);
        push("Importación cancelada. Escenario parcial eliminado.", "info");
      } catch {
        push("Importación cancelada. No se pudo eliminar el escenario parcial.", "error");
      }
    }
    setOpenExcel(false);
    resetExcelModal();
    await fetchScenarios();
  }

  function resetConcatModal() {
    setConcatBaseFile(null);
    setConcatNewFiles([]);
    setConcatDropTechs("");
    setConcatDropFuels("");
    setConcatIncludeLogTxt(false);
    setConcatUploadPhase("idle");
    setConcatUploadPercent(0);
    setConcatUploadStartedAt(null);
    setConcatErrorDetail(null);
    setConcatErrorExpanded(false);
    setConcatDoneConflictsDetail(null);
    setConcatDoneConflictsExpanded(false);
    setConcatDoneConflictCount(0);
    setConcatExportVerification(null);
  }

  async function handleCloseConcatSand() {
    if (concatingSand) {
      concatAbortRef.current?.abort();
      concatAbortRef.current = null;
      setConcatingSand(false);
    }
    setOpenConcatSand(false);
    resetConcatModal();
  }

  async function handleConcatenateSand() {
    if (!concatBaseFile) {
      push("Selecciona un archivo base SAND.", "error");
      return;
    }
    if (!concatNewFiles.length) {
      push("Selecciona al menos un archivo nuevo SAND.", "error");
      return;
    }

    const abortCtrl = new AbortController();
    concatAbortRef.current = abortCtrl;
    setConcatingSand(true);
    setConcatUploadPhase("uploading");
    setConcatUploadPercent(0);
    setConcatUploadStartedAt(Date.now());
    setConcatErrorDetail(null);
    setConcatErrorExpanded(false);
    setConcatDoneConflictsDetail(null);
    setConcatDoneConflictsExpanded(false);
    setConcatDoneConflictCount(0);
    setConcatExportVerification(null);

    try {
      const { blob, filename, summary } = await scenariosApi.concatenateSand(
        {
          baseFile: concatBaseFile,
          newFiles: concatNewFiles,
          dropTechs: concatDropTechs,
          dropFuels: concatDropFuels,
          includeLogTxt: concatIncludeLogTxt,
        },
        (percent) => {
          setConcatUploadPercent(percent);
          if (percent >= 100) setConcatUploadPhase("processing");
        },
        abortCtrl.signal,
      );

      if (summary.integration_failed) {
        setConcatUploadPhase("error");
        setConcatErrorDetail(formatSandIntegrationFailureDetail(summary));

        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);

        push(
          "La integración falló. Se descargó el informe (log o ZIP con el log). Revisa el detalle con «Ver más».",
          "error",
        );
        return;
      }

      setConcatUploadPhase("done");
      setConcatExportVerification(summary.export_verification ?? null);

      if (summary.conflictos_count > 0) {
        setConcatDoneConflictCount(summary.conflictos_count);
        setConcatDoneConflictsDetail(
          formatSandConflictsDetail(summary.conflictos ?? [], summary.conflictos_count),
        );
        setConcatDoneConflictsExpanded(false);
      } else {
        setConcatDoneConflictCount(0);
        setConcatDoneConflictsDetail(null);
      }

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      if (summary.conflictos_count > 0) {
        push(
          `Integración con ${summary.conflictos_count} conflicto(s) entre archivos nuevos. Se descargó un ZIP con ` +
            `integracion_sand_log.txt y conflictos_integracion.xlsx. No se incluye el Excel integrado ni cambios_integracion.xlsx.` +
            (summary.log_line_count
              ? ` El informe de texto tiene ${summary.log_line_count} línea(s).`
              : ""),
          "success",
        );
      } else {
        push(
          `Integración completada: ${summary.total_filas.toLocaleString()} filas, 0 conflictos.${
            summary.has_log && summary.log_line_count
              ? ` ZIP con informe detallado (${summary.log_line_count} líneas en el .txt${
                  summary.has_cambios_xlsx ? ", Excel cambios_integracion.xlsx" : ""
                }).`
              : ""
          }`,
          "success",
        );
      }
      if (summary.warnings.length) {
        push(`La integración reportó ${summary.warnings.length} advertencia(s).`, "info");
      }
      if (summary.errors.length) {
        push(`La integración reportó ${summary.errors.length} error(es) de validación.`, "error");
      }
    } catch (err) {
      if (abortCtrl.signal.aborted) return;
      setConcatUploadPhase("error");
      setConcatExportVerification(null);
      setConcatErrorDetail(formatConcatAxiosErrorDetail(err));
      setConcatErrorExpanded(false);
      push(err instanceof Error ? err.message : "No se pudo concatenar archivos SAND.", "error");
    } finally {
      setConcatingSand(false);
      concatAbortRef.current = null;
    }
  }

  function resetVerifyModal() {
    setVerifyBaseFile(null);
    setVerifyNewFiles([]);
    setVerifyIntegratedFile(null);
    setVerifyDropTechs("");
    setVerifyDropFuels("");
    setVerifyUploadPhase("idle");
    setVerifyUploadPercent(0);
    setVerifyUploadStartedAt(null);
    setVerifyResult(null);
  }

  function handleCloseVerifySand() {
    if (verifyUploadPhase === "uploading" || verifyUploadPhase === "processing") {
      verifyAbortRef.current?.abort();
      verifyAbortRef.current = null;
    }
    setOpenVerifySand(false);
    resetVerifyModal();
  }

  async function handleVerifySandIntegration() {
    if (!verifyBaseFile || !verifyIntegratedFile || !verifyNewFiles.length) {
      push("Selecciona archivo base, al menos un archivo nuevo y el Excel integrado.", "error");
      return;
    }
    const abortCtrl = new AbortController();
    verifyAbortRef.current = abortCtrl;
    setVerifyUploadPhase("uploading");
    setVerifyUploadPercent(0);
    setVerifyUploadStartedAt(Date.now());
    setVerifyResult(null);
    try {
      const res = await scenariosApi.verifySandIntegration(
        {
          baseFile: verifyBaseFile,
          integratedFile: verifyIntegratedFile,
          newFiles: verifyNewFiles,
          dropTechs: verifyDropTechs,
          dropFuels: verifyDropFuels,
        },
        (percent) => {
          setVerifyUploadPercent(percent);
          if (percent >= 100) setVerifyUploadPhase("processing");
        },
        abortCtrl.signal,
      );
      setVerifyResult(res.export_verification);
      setVerifyUploadPhase("done");
      push(
        res.export_verification.ok
          ? "Validación: el integrado coincide con los cambios esperados."
          : "Validación: hay discrepancias entre el integrado y los cambios esperados.",
        res.export_verification.ok ? "success" : "error",
      );
    } catch (err) {
      if (abortCtrl.signal.aborted) return;
      setVerifyUploadPhase("error");
      push(err instanceof Error ? err.message : "No se pudo verificar la integración.", "error");
    } finally {
      verifyAbortRef.current = null;
    }
  }

  const verifyFileSizeBytes =
    (verifyBaseFile?.size ?? 0) +
    (verifyIntegratedFile?.size ?? 0) +
    verifyNewFiles.reduce((s, f) => s + f.size, 0);

  return (
    <section className="pageSection scenariosPage">
      <div className="toolbarRow scenariosPage__header">
        <div>
          <h1 style={{ margin: 0 }}>Escenarios</h1>
          <p style={{ margin: "6px 0 0", opacity: 0.75 }}>
            Lista global con filtros por nombre, propietario y política de edición.
          </p>
        </div>
        <div className="scenariosPage__actions">
          <Button
            variant="primary"
            onClick={() => {
              setTagSelectCreate("");
              setOpenCreate(true);
            }}
            className="scenariosPage__actionButton"
          >
            Crear escenario
          </Button>
          {user?.can_manage_catalogs ? (
            <Button variant="ghost" onClick={() => setOpenTagsCatalog(true)} className="scenariosPage__actionButton">
              Etiquetas
            </Button>
          ) : null}
          <Button variant="ghost" onClick={() => setOpenExcel(true)} className="scenariosPage__actionButton">
            Crear desde Excel
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              resetCsvModal();
              setOpenCsv(true);
            }}
            className="scenariosPage__actionButton"
          >
            Crear desde CSV
          </Button>
          <Button variant="ghost" onClick={() => setOpenConcatSand(true)} className="scenariosPage__actionButton">
            Concatenar SAND
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              resetVerifyModal();
              setOpenVerifySand(true);
            }}
            className="scenariosPage__actionButton"
          >
            Verificar integración
          </Button>
        </div>
      </div>

      <div className="scenariosPage__filters">
        <TextField
          label="Buscar por nombre"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Escenario, descripción o owner"
        />
        <TextField
          label="Filtrar por propietario"
          value={ownerFilter}
          onChange={(e) => setOwnerFilter(e.target.value)}
          placeholder="username"
        />
        <label className="field">
          <span className="field__label">Política</span>
          <select
            className="field__input"
            value={policyFilter}
            onChange={(e) => setPolicyFilter(e.target.value as ScenarioEditPolicy | "ALL")}
          >
            <option value="ALL">Todas</option>
            <option value="OWNER_ONLY">Solo propietario</option>
            <option value="OPEN">Abierta</option>
            <option value="RESTRICTED">Restringida</option>
          </select>
        </label>
        <Button
          variant="ghost"
          className="scenariosPage__filterButton"
          onClick={() => {
            setPage(1);
            void fetchScenarios();
          }}
          disabled={loadingRows}
        >
          Aplicar filtros
        </Button>
      </div>

      <div style={{ overflowX: "auto", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ background: "rgba(255,255,255,0.03)" }}>
            <tr>
              {["Escenario", "Etiqueta", "Descripción", "Política", "Propietario", "Creado", "Proceso", ""].map((header) => (
                <th key={header} style={{ textAlign: "left", fontSize: 13, padding: "10px 12px", color: "var(--muted)" }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loadingRows ? (
              <tr>
                <td colSpan={8} style={{ padding: 14, opacity: 0.75 }}>
                  Cargando escenarios...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: 14, opacity: 0.75 }}>
                  Sin registros.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id} style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                  {(() => {
                    const cloneJob =
                      cloneJobs.find((j) => j.target_scenario_id === row.id) ??
                      cloneJobs.find(
                        (j) =>
                          j.scenario_id === row.id &&
                          (j.status === "QUEUED" || j.status === "RUNNING"),
                      );
                    return (
                      <>
                  <td style={{ padding: "10px 12px" }}>
                    <button
                      type="button"
                      className="btn btn--ghost scenariosPage__nameButton"
                      onClick={() => navigate(paths.scenarioDetail(row.id))}
                    >
                      {row.name}
                    </button>
                    {row.base_scenario_id ? (
                      <div className="scenariosPage__nameMeta">
                        Hijo de {row.base_scenario_name ?? `#${row.base_scenario_id}`}
                      </div>
                    ) : null}
                  </td>
                  <td style={{ padding: "10px 12px", verticalAlign: "top" }}>
                    <div className="scenariosPage__tagCell">
                      {row.tag ? (
                        <ScenarioTagChip tag={row.tag} />
                      ) : (
                        <span className="scenariosPage__tagCellEmpty">—</span>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: "10px 12px" }}>{row.description ?? "—"}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ display: "grid", gap: 4 }}>
                      <Badge variant="info">{editPolicyLabel[row.edit_policy]}</Badge>
                      <small style={{ opacity: 0.7 }}>{editPolicyHelp[row.edit_policy]}</small>
                    </div>
                  </td>
                  <td style={{ padding: "10px 12px" }}>{row.owner}</td>
                  <td style={{ padding: "10px 12px" }}>{new Date(row.created_at).toLocaleString()}</td>
                  <td style={{ padding: "10px 12px" }}>
                    {cloneJob ? (
                      <div style={{ display: "grid", gap: 4 }}>
                        <Badge
                          variant={
                            cloneJob.status === "SUCCEEDED"
                              ? "success"
                              : cloneJob.status === "FAILED"
                                ? "danger"
                                : "info"
                          }
                        >
                          {cloneJob.status} · {Math.round(cloneJob.progress)}%
                        </Badge>
                        <small style={{ opacity: 0.75 }}>{cloneJob.message ?? cloneJob.stage ?? "Procesando..."}</small>
                      </div>
                    ) : (
                      <span style={{ opacity: 0.65 }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <Button
                        variant="ghost"
                        onClick={() => void handleDownloadExcel(row)}
                        disabled={downloadingScenarioId === row.id}
                        style={{ padding: "4px 10px", fontSize: "0.85rem" }}
                      >
                        {downloadingScenarioId === row.id ? "Descargando..." : "Descargar"}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setCloneSourceId(row.id);
                          setCloneName(buildCloneName(row.name));
                          setCloneEditPolicy(row.edit_policy);
                          setOpenClone(true);
                        }}
                        style={{ padding: "4px 10px", fontSize: "0.85rem" }}
                      >
                        Copiar
                      </Button>
                      {canAssignScenarioTag(row) ? (
                        <Button
                          variant="ghost"
                          type="button"
                          onClick={() => openScenarioTagModal(row)}
                          disabled={tagModalSaving}
                          style={{ padding: "4px 10px", fontSize: "0.85rem" }}
                        >
                          Etiqueta
                        </Button>
                      ) : null}
                    </div>
                  </td>
                      </>
                    );
                  })()}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {cloneJobs.some((j) => (j.status === "QUEUED" || j.status === "RUNNING") && !j.target_scenario_id) ? (
        <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: 10 }}>
          <strong style={{ fontSize: 13 }}>Copias en preparación</strong>
          <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
            {cloneJobs
              .filter((j) => (j.status === "QUEUED" || j.status === "RUNNING") && !j.target_scenario_id)
              .map((job) => (
                <div key={job.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <Badge variant="info">{job.status}</Badge>
                  <span style={{ fontSize: 13, opacity: 0.85 }}>{Math.round(job.progress)}%</span>
                  <span style={{ fontSize: 13, opacity: 0.75 }}>{job.message ?? job.stage ?? "Procesando..."}</span>
                </div>
              ))}
          </div>
        </div>
      ) : null}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <small style={{ opacity: 0.75 }}>
            Página {page} de {totalPages}
          </small>
          <small style={{ opacity: 0.75 }}>
            · {total.toLocaleString()} escenarios visibles
          </small>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, opacity: 0.85 }}>
            Por página:
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value) || 25);
                setPage(1);
              }}
              style={{ padding: "2px 6px", borderRadius: 6, background: "transparent", color: "inherit" }}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn--ghost" type="button" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
              Anterior
            </button>
            <button className="btn btn--ghost" type="button" disabled={page >= totalPages} onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}>
              Siguiente
            </button>
          </div>
        </div>
      </div>

      <Modal
        open={openCreate}
        title="Crear escenario"
        onClose={() => setOpenCreate(false)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setOpenCreate(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleCreate} disabled={saving}>
              {saving ? "Guardando..." : "Crear"}
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          <TextField label="Nombre" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField label="Descripción" value={description} onChange={(e) => setDescription(e.target.value)} />
          <label className="field">
            <span className="field__label">Política de edición</span>
            <select
              className="field__input"
              value={editPolicy}
              onChange={(e) => setEditPolicy(e.target.value as ScenarioEditPolicy)}
            >
              <option value="OWNER_ONLY">Solo propietario</option>
              <option value="OPEN">Abierta</option>
              <option value="RESTRICTED">Restringida</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Tipo de simulación</span>
            <select
              className="field__input"
              value={simulationType}
              onChange={(e) => setSimulationType(e.target.value as SimulationType)}
            >
              <option value="NATIONAL">{simulationTypeLabel.NATIONAL}</option>
              <option value="REGIONAL">{simulationTypeLabel.REGIONAL}</option>
            </select>
          </label>
          <small style={{ opacity: 0.75 }}>{editPolicyHelp[editPolicy]}</small>
          <label className="field">
            <span className="field__label">Etiqueta (opcional)</span>
            <select
              className="field__input"
              value={tagSelectCreate}
              onChange={(e) => setTagSelectCreate(e.target.value)}
            >
              <option value="">Sin etiqueta</option>
              {scenarioTags.map((t) => (
                <option key={t.id} value={String(t.id)}>
                  {t.name} (prioridad {t.sort_order})
                </option>
              ))}
            </select>
          </label>
        </div>
      </Modal>

      <Modal
        open={tagModalScenario !== null}
        title={tagModalScenario ? `Etiqueta — ${tagModalScenario.name}` : "Etiqueta"}
        onClose={closeScenarioTagModal}
        footer={
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 8,
              width: "100%",
            }}
          >
            <div>
              {tagModalScenario?.tag ? (
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() => void removeScenarioTagFromModal()}
                  disabled={tagModalSaving}
                  style={{ color: "rgba(248,113,113,0.95)" }}
                >
                  Quitar etiqueta
                </Button>
              ) : null}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Button variant="ghost" onClick={closeScenarioTagModal} disabled={tagModalSaving}>
                Cancelar
              </Button>
              <Button variant="primary" onClick={() => void saveScenarioTagModal()} disabled={tagModalSaving}>
                {tagModalSaving ? "Guardando..." : "Guardar"}
              </Button>
            </div>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 14 }}>
          {tagModalScenario?.tag ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, opacity: 0.75 }}>Etiqueta actual</span>
              <ScenarioTagChip tag={tagModalScenario.tag} />
            </div>
          ) : null}
          <label className="field">
            <span className="field__label">{tagModalScenario?.tag ? "Cambiar a" : "Asignar"}</span>
            <select
              className="field__input"
              value={tagModalSelection}
              onChange={(e) => setTagModalSelection(e.target.value)}
              disabled={!scenarioTags.length}
            >
              <option value="">Sin etiqueta</option>
              {scenarioTags.map((t) => (
                <option key={t.id} value={String(t.id)}>
                  {t.name} (prioridad {t.sort_order})
                </option>
              ))}
            </select>
          </label>
          {!scenarioTags.length ? (
            <p style={{ margin: 0, fontSize: 12, opacity: 0.75 }}>Crea entradas en el catálogo con «Etiquetas».</p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={openExcel}
        title="Crear escenario desde Excel"
        onClose={handleCloseExcel}
        disableBackdropClose
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={handleCloseExcel}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleCreateFromExcel} disabled={importing}>
              {importing ? "Importando..." : "Crear e importar"}
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          <label className="field">
            <span className="field__label">Archivo Excel (.xlsm/.xlsx)</span>
            <input
              className="field__input"
              type="file"
              accept=".xlsm,.xlsx"
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                setExcelFile(file);
                setExcelSheets([]);
                setSelectedSheet("");
              }}
            />
          </label>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button variant="ghost" onClick={() => void loadSheets()} disabled={!excelFile || loadingSheets}>
              {loadingSheets ? "Leyendo hojas..." : "Listar hojas"}
            </Button>
            <small style={{ opacity: 0.75 }}>Para archivos grandes, este paso puede tardar unos segundos.</small>
          </div>

          <label className="field">
            <span className="field__label">Hoja a importar</span>
            <select
              className="field__input"
              value={selectedSheet}
              onChange={(e) => setSelectedSheet(e.target.value)}
              disabled={!excelSheets.length}
            >
              <option value="">{excelSheets.length ? "Selecciona..." : "Primero lista las hojas"}</option>
              {excelSheets.map((sheet) => (
                <option key={sheet} value={sheet}>
                  {sheet}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Tipo de simulación</span>
            <select
              className="field__input"
              value={simulationType}
              onChange={(e) => setSimulationType(e.target.value as SimulationType)}
            >
              <option value="NATIONAL">{simulationTypeLabel.NATIONAL}</option>
              <option value="REGIONAL">{simulationTypeLabel.REGIONAL}</option>
            </select>
          </label>

          <TextField label="Nombre" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField label="Descripción" value={description} onChange={(e) => setDescription(e.target.value)} />
          <label className="field">
            <span className="field__label">Política de edición</span>
            <select
              className="field__input"
              value={editPolicy}
              onChange={(e) => setEditPolicy(e.target.value as ScenarioEditPolicy)}
            >
              <option value="OWNER_ONLY">Solo propietario</option>
              <option value="OPEN">Abierta</option>
              <option value="RESTRICTED">Restringida</option>
            </select>
          </label>
          <small style={{ opacity: 0.75 }}>{editPolicyHelp[editPolicy]}</small>
          <label className="field">
            <span className="field__label">Etiqueta (opcional)</span>
            <select
              className="field__input"
              value={tagSelectExcel}
              onChange={(e) => setTagSelectExcel(e.target.value)}
            >
              <option value="">Sin etiqueta</option>
              {scenarioTags.map((t) => (
                <option key={t.id} value={String(t.id)}>
                  {t.name} (prioridad {t.sort_order})
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", userSelect: "none", fontSize: 13 }}>
            <input
              type="checkbox"
              checked={includeUdcExcel}
              onChange={(e) => setIncludeUdcExcel(e.target.checked)}
            />
            Incluir restricción UDC de Reserva de Margen de Capacidad
          </label>

          {excelUploadPhase !== "idle" ? (
            <UploadProgress
              phase={excelUploadPhase}
              uploadPercent={excelUploadPercent}
              fileSizeBytes={excelFile?.size ?? 0}
              startedAt={excelUploadStartedAt}
            />
          ) : null}
        </div>
      </Modal>

      <Modal
        open={openCsv}
        title="Crear escenario desde CSV"
        onClose={() => {
          setOpenCsv(false);
          resetCsvModal();
        }}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button
              variant="ghost"
              onClick={() => {
                setOpenCsv(false);
                resetCsvModal();
              }}
            >
              Cancelar
            </Button>
            <Button variant="primary" onClick={() => void handleCreateFromCsv()} disabled={csvImporting}>
              {csvImporting ? "Importando..." : "Crear e importar"}
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          <label className="field">
            <span className="field__label">ZIP con CSV procesados</span>
            <input
              className="field__input"
              type="file"
              accept=".zip,application/zip"
              onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <TextField label="Nombre" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField label="Descripción" value={description} onChange={(e) => setDescription(e.target.value)} />
          <label className="field">
            <span className="field__label">Política de edición</span>
            <select
              className="field__input"
              value={editPolicy}
              onChange={(e) => setEditPolicy(e.target.value as ScenarioEditPolicy)}
            >
              <option value="OWNER_ONLY">Solo propietario</option>
              <option value="OPEN">Abierta</option>
              <option value="RESTRICTED">Restringida</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Tipo de simulación</span>
            <select
              className="field__input"
              value={simulationType}
              onChange={(e) => setSimulationType(e.target.value as SimulationType)}
            >
              <option value="NATIONAL">{simulationTypeLabel.NATIONAL}</option>
              <option value="REGIONAL">{simulationTypeLabel.REGIONAL}</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Etiqueta (opcional)</span>
            <select
              className="field__input"
              value={tagSelectExcel}
              onChange={(e) => setTagSelectExcel(e.target.value)}
            >
              <option value="">Sin etiqueta</option>
              {scenarioTags.map((t) => (
                <option key={t.id} value={String(t.id)}>
                  {t.name} (prioridad {t.sort_order})
                </option>
              ))}
            </select>
          </label>
        </div>
      </Modal>

      <Modal
        open={openTagsCatalog}
        title="Catálogo de etiquetas"
        onClose={() => setOpenTagsCatalog(false)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setOpenTagsCatalog(false)}>
              Cerrar
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 14 }}>
          <p style={{ margin: 0, fontSize: 13, opacity: 0.85 }}>
            Las etiquetas definen prioridad en listados (menor número = más arriba) y color en la interfaz. Solo
            administradores de catálogo pueden crear o eliminar etiquetas; cualquier usuario con permiso de edición
            del escenario puede asignarlas.
          </p>
          <div style={{ display: "grid", gap: 8, padding: 12, border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10 }}>
            <strong style={{ fontSize: 13 }}>Nueva etiqueta</strong>
            <TextField label="Nombre" value={tagCatName} onChange={(e) => setTagCatName(e.target.value)} />
            <div className="field" style={{ margin: 0 }}>
              <span className="field__label">Color</span>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(8, minmax(0, 1fr))",
                  gap: 8,
                  marginTop: 6,
                }}
              >
                {SCENARIO_TAG_COLOR_PALETTE.map((hex) => {
                  const selected = normalizeTagHex(tagCatColor) === hex;
                  return (
                    <button
                      key={hex}
                      type="button"
                      title={hex}
                      onClick={() => setTagCatColor(hex)}
                      aria-label={`Color ${hex}`}
                      aria-pressed={selected}
                      style={{
                        width: "100%",
                        aspectRatio: "1",
                        maxWidth: 36,
                        borderRadius: 8,
                        border: selected ? "2px solid #fff" : "2px solid rgba(255,255,255,0.2)",
                        boxShadow: selected ? "0 0 0 2px rgba(59,130,246,0.5)" : "none",
                        backgroundColor: hex,
                        cursor: "pointer",
                        padding: 0,
                      }}
                    />
                  );
                })}
              </div>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  marginTop: 12,
                  fontSize: 13,
                  opacity: 0.9,
                }}
              >
                <span>Otro color</span>
                <input
                  type="color"
                  aria-label="Elegir otro color"
                  value={/^#[0-9A-Fa-f]{6}$/i.test(tagCatColor.trim()) ? tagCatColor.trim().slice(0, 7) : "#3B82F6"}
                  onChange={(e) => setTagCatColor(e.target.value.toUpperCase())}
                  style={{
                    width: 44,
                    height: 32,
                    padding: 0,
                    border: "1px solid rgba(255,255,255,0.2)",
                    borderRadius: 8,
                    cursor: "pointer",
                    background: "transparent",
                  }}
                />
              </label>
            </div>
            <TextField label="Orden (prioridad)" value={tagCatSort} onChange={(e) => setTagCatSort(e.target.value)} />
            <Button variant="primary" onClick={() => void handleAddCatalogTag()} disabled={savingCatalogTag}>
              {savingCatalogTag ? "Guardando..." : "Crear etiqueta"}
            </Button>
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            <strong style={{ fontSize: 13 }}>Existentes</strong>
            {scenarioTags.length === 0 ? (
              <span style={{ opacity: 0.7 }}>No hay etiquetas.</span>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
                {scenarioTags.map((t) => (
                  <li key={t.id} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <ScenarioTagChip tag={t} />
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        fontSize: 12,
                        opacity: 0.75,
                      }}
                    >
                      orden {t.sort_order}
                      <span
                        title={t.color}
                        style={{
                          width: 14,
                          height: 14,
                          borderRadius: 4,
                          backgroundColor: t.color,
                          border: "1px solid rgba(255,255,255,0.25)",
                        }}
                      />
                    </span>
                    <Button variant="ghost" type="button" onClick={() => void handleDeleteCatalogTag(t.id)} style={{ padding: "2px 8px" }}>
                      Eliminar
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </Modal>

      <Modal
        open={openClone}
        title="Copiar escenario"
        onClose={resetCloneModal}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button
              variant="ghost"
              onClick={resetCloneModal}
            >
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleClone} disabled={cloning}>
              {cloning ? "Copiando..." : "Copiar"}
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          <TextField
            label="Nombre del nuevo escenario"
            value={cloneName}
            onChange={(e) => setCloneName(e.target.value)}
          />
          <label className="field">
            <span className="field__label">Política de edición</span>
            <select
              className="field__input"
              value={cloneEditPolicy}
              onChange={(e) => setCloneEditPolicy(e.target.value as ScenarioEditPolicy)}
            >
              <option value="OWNER_ONLY">Solo propietario</option>
              <option value="OPEN">Abierta</option>
              <option value="RESTRICTED">Restringida</option>
            </select>
          </label>
          <small style={{ opacity: 0.75 }}>{editPolicyHelp[cloneEditPolicy]}</small>
        </div>
      </Modal>

      <Modal
        open={openConcatSand}
        title="Concatenar archivos SAND"
        onClose={handleCloseConcatSand}
        disableBackdropClose
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={handleCloseConcatSand}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleConcatenateSand} disabled={concatingSand}>
              {concatingSand ? "Integrando..." : "Integrar"}
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          <label className="field">
            <span className="field__label">Archivo base (.xlsm/.xlsx)</span>
            <input
              className="field__input"
              type="file"
              accept=".xlsm,.xlsx"
              onChange={(e) => setConcatBaseFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <label className="field">
            <span className="field__label">Archivos nuevos a integrar (.xlsm/.xlsx)</span>
            <input
              className="field__input"
              type="file"
              accept=".xlsm,.xlsx"
              multiple
              onChange={(e) => setConcatNewFiles(Array.from(e.target.files ?? []))}
            />
          </label>
          <small style={{ opacity: 0.75 }}>
            Seleccionados: {concatNewFiles.length} archivo(s)
          </small>

          <TextField
            label="Tecnologías a eliminar (CSV, opcional)"
            value={concatDropTechs}
            onChange={(e) => setConcatDropTechs(e.target.value)}
            placeholder="Ejemplo: MINOIL,TECH_X"
          />
          <TextField
            label="Fuels a eliminar (CSV, opcional)"
            value={concatDropFuels}
            onChange={(e) => setConcatDropFuels(e.target.value)}
            placeholder="Ejemplo: OIL,GAS"
          />

          <label className="field" style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={concatIncludeLogTxt}
              onChange={(e) => setConcatIncludeLogTxt(e.target.checked)}
            />
            <span>
              Incluir informe detallado (solo si no hay conflictos entre archivos nuevos): ZIP con el Excel integrado,
              integracion_sand_log.txt y cambios_integracion.xlsx (cambios vs base, duplicados, validación, drop). Si
              hay conflictos, la descarga es otro ZIP solo con el .txt y conflictos_integracion.xlsx.
            </span>
          </label>

          {concatUploadPhase !== "idle" ? (
            <UploadProgress
              phase={concatUploadPhase}
              uploadPercent={concatUploadPercent}
              fileSizeBytes={concatBaseFile?.size ?? 0}
              startedAt={concatUploadStartedAt}
              {...(concatUploadPhase === "done" && concatDoneConflictCount > 0
                ? { doneLabel: "Conflictos" as const, doneVariant: "conflicts" as const }
                : {})}
            />
          ) : null}

          {concatUploadPhase === "done" && concatExportVerification && concatDoneConflictCount === 0 ? (
            <SandExportVerificationPanel data={concatExportVerification} variant="concatenate" />
          ) : null}

          {concatUploadPhase === "error" && concatErrorDetail ? (
            <div style={{ display: "grid", gap: 8 }}>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setConcatErrorExpanded((v) => !v)}
                style={{ justifySelf: "start", paddingLeft: 0 }}
              >
                {concatErrorExpanded ? "Ver menos" : "Ver más"}
              </Button>
              {concatErrorExpanded ? (
                <pre
                  style={{
                    margin: 0,
                    padding: 12,
                    fontSize: 12,
                    lineHeight: 1.45,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    borderRadius: 8,
                    border: "1px solid rgba(255,255,255,0.12)",
                    background: "rgba(0,0,0,0.25)",
                    maxHeight: 280,
                    overflow: "auto",
                  }}
                >
                  {concatErrorDetail}
                </pre>
              ) : null}
            </div>
          ) : null}

          {concatUploadPhase === "done" && concatDoneConflictsDetail ? (
            <div style={{ display: "grid", gap: 8 }}>
              <p style={{ margin: 0, fontSize: 13, opacity: 0.9 }}>
                Hay {concatDoneConflictCount} conflicto(s) entre los archivos nuevos. El ZIP descargado incluye el
                informe integracion_sand_log.txt y conflictos_integracion.xlsx; no se incluyó el Excel integrado ni el
                informe amplio de cambios. Los cambios se aplicaron en memoria en orden; revisa qué archivos proponen
                valores distintos.
              </p>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setConcatDoneConflictsExpanded((v) => !v)}
                style={{ justifySelf: "start", paddingLeft: 0 }}
              >
                {concatDoneConflictsExpanded ? "Ver menos" : "Ver más — detalle de conflictos"}
              </Button>
              {concatDoneConflictsExpanded ? (
                <pre
                  style={{
                    margin: 0,
                    padding: 12,
                    fontSize: 12,
                    lineHeight: 1.45,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    borderRadius: 8,
                    border: "1px solid rgba(255,255,255,0.12)",
                    background: "rgba(0,0,0,0.25)",
                    maxHeight: 280,
                    overflow: "auto",
                  }}
                >
                  {concatDoneConflictsDetail}
                </pre>
              ) : null}
            </div>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={openVerifySand}
        title="Verificar integración SAND"
        onClose={handleCloseVerifySand}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={handleCloseVerifySand}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => void handleVerifySandIntegration()}
              disabled={
                verifyUploadPhase === "uploading" ||
                verifyUploadPhase === "processing" ||
                !verifyBaseFile ||
                !verifyIntegratedFile ||
                verifyNewFiles.length === 0
              }
            >
              {verifyUploadPhase === "uploading" || verifyUploadPhase === "processing"
                ? "Verificando..."
                : "Verificar"}
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 12, maxHeight: "min(70vh, 640px)", overflowY: "auto" }}>
          <p style={{ margin: 0, fontSize: 13, opacity: 0.85 }}>
            Sube el mismo archivo base, los Excel nuevos que integraste (en el mismo orden si aplica) y el Excel
            integrado resultante. Opcionalmente indica tecnologías y fuels eliminados por drop, como en concatenar
            SAND.
          </p>
          <label className="field">
            <span className="field__label">Archivo base (.xlsm/.xlsx)</span>
            <input
              className="field__input"
              type="file"
              accept=".xlsm,.xlsx"
              onChange={(e) => setVerifyBaseFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label className="field">
            <span className="field__label">Archivos nuevos a comprobar (.xlsm/.xlsx)</span>
            <input
              className="field__input"
              type="file"
              accept=".xlsm,.xlsx"
              multiple
              onChange={(e) => setVerifyNewFiles(Array.from(e.target.files ?? []))}
            />
          </label>
          <small style={{ opacity: 0.75 }}>Seleccionados: {verifyNewFiles.length} archivo(s)</small>
          <label className="field">
            <span className="field__label">Excel integrado a validar (.xlsm/.xlsx)</span>
            <input
              className="field__input"
              type="file"
              accept=".xlsm,.xlsx"
              onChange={(e) => setVerifyIntegratedFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <TextField
            label="Tecnologías a eliminar (CSV, opcional)"
            value={verifyDropTechs}
            onChange={(e) => setVerifyDropTechs(e.target.value)}
            placeholder="Ejemplo: MINOIL,TECH_X"
          />
          <TextField
            label="Fuels a eliminar (CSV, opcional)"
            value={verifyDropFuels}
            onChange={(e) => setVerifyDropFuels(e.target.value)}
            placeholder="Ejemplo: OIL,GAS"
          />

          {verifyUploadPhase !== "idle" ? (
            <UploadProgress
              phase={verifyUploadPhase}
              uploadPercent={verifyUploadPercent}
              fileSizeBytes={verifyFileSizeBytes}
              startedAt={verifyUploadStartedAt}
              {...(verifyUploadPhase === "done" && verifyResult
                ? verifyResult.ok
                  ? { doneLabel: "Verificación completada" }
                  : { doneLabel: "Verificación con discrepancias", doneVariant: "conflicts" as const }
                : {})}
            />
          ) : null}

          {verifyResult ? (
            <SandExportVerificationPanel data={verifyResult} variant="standalone" />
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
