/**
 * ScenarioDetailPage - Detalle de un escenario energético
 *
 * Tres pestañas principales:
 * 1. Valores: parámetros OSeMOSYS (osemosys_param_value), filtros por parámetro/año, CRUD de valores,
 *    resumen agregado, propuestas de cambio para usuarios sin edición directa
 * 2. Permisos: gestión de permisos (can_edit_direct, can_propose, can_manage_values) para usuarios
 * 3. Solicitudes pendientes: aprobar/rechazar cambios propuestos por otros usuarios
 *
 * Endpoints usados:
 * - scenariosApi.getScenarioById, getEffectivePermission
 * - scenariosApi.listOsemosysSummary, listOsemosysValues (con filtros param_name, year)
 * - scenariosApi.createOsemosysValue, updateOsemosysValue, deactivateOsemosysValue
 * - scenariosApi.createChangeRequest, listPendingChangeRequests, reviewChangeRequest
 * - scenariosApi.listPermissions, upsertPermission
 *
 * La visibilidad de acciones depende de la política del escenario (OWNER_ONLY, OPEN, RESTRICTED).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { useToast } from "@/app/providers/useToast";
import {
  scenariosApi,
  type ExcelUpdatePreviewRow,
  type OsemosysValueRow,
  type OsemosysYearSummary,
  type ScenarioAccess,
} from "@/features/scenarios/api/scenariosApi";
import { officialImportApi } from "@/features/officialImport/api/officialImportApi";
import { catalogsApi } from "@/features/catalogs/api/catalogsApi";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { ScenarioTagChip } from "@/shared/components/ScenarioTagChip";
import { DataTable } from "@/shared/components/DataTable";
import { Modal } from "@/shared/components/Modal";
import { TextField } from "@/shared/components/TextField";
import { UploadProgress, type UploadPhase } from "@/shared/components/UploadProgress";
import type {
  ChangeRequest,
  Scenario,
  ScenarioEditPolicy,
  ScenarioOperationJob,
  ScenarioPermission,
  ScenarioTag,
  SimulationType,
} from "@/types/domain";

type Tab = "values" | "permissions" | "pending";

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200] as const;
const PREVIEW_PAGE_SIZE_OPTIONS = [100, 200, 500, 1000] as const;
const PREVIEW_NARROW_BREAKPOINT = 920;

type PreviewGroup = {
  key: string;
  param_name: string;
  region_name: string | null;
  technology_name: string | null;
  fuel_name: string | null;
  emission_name: string | null;
  rows: ExcelUpdatePreviewRow[];
};

function buildPreviewGroupKey(row: ExcelUpdatePreviewRow): string {
  return [
    row.param_name,
    row.region_name ?? "",
    row.technology_name ?? "",
    row.fuel_name ?? "",
    row.emission_name ?? "",
  ].join("||");
}

function getPolicyExplanation(editPolicy: ScenarioEditPolicy): string {
  if (editPolicy === "OWNER_ONLY") return "Solo el propietario administra permisos y edita valores.";
  if (editPolicy === "OPEN") return "Cualquier usuario autenticado con acceso al escenario puede editar valores.";
  return "Solo permisos explícitos pueden editar o gestionar valores.";
}

export function ScenarioDetailPage() {
  const { id } = useParams<{ id: string }>();
  const scenarioId = Number(id);
  const { user } = useCurrentUser();
  const { push } = useToast();
  const [tab, setTab] = useState<Tab>("values");
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [access, setAccess] = useState<ScenarioAccess | null>(null);
  const [osemosysRows, setOsemosysRows] = useState<OsemosysValueRow[]>([]);
  const [osemosysTotal, setOsemosysTotal] = useState(0);
  const [osemosysPage, setOsemosysPage] = useState(1);
  const [osemosysPageSize, setOsemosysPageSize] = useState<number>(50);
  const [osemosysSearch, setOsemosysSearch] = useState("");
  const [osemosysLoading, setOsemosysLoading] = useState(false);
  const [osemosysSummary, setOsemosysSummary] = useState<OsemosysYearSummary[]>([]);
  const [filterParamName, setFilterParamName] = useState("");
  const [filterYear, setFilterYear] = useState("");
  const [permissions, setPermissions] = useState<ScenarioPermission[]>([]);
  const [pending, setPending] = useState<ChangeRequest[]>([]);
  const [parentScenarioName, setParentScenarioName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [openOsemosysModal, setOpenOsemosysModal] = useState(false);
  const [editingOsemosys, setEditingOsemosys] = useState<OsemosysValueRow | null>(null);
  const [proposeFor, setProposeFor] = useState<OsemosysValueRow | null>(null);
  const [proposalNewValue, setProposalNewValue] = useState("");

  const [openExcelUpdateModal, setOpenExcelUpdateModal] = useState(false);
  const [excelUpdateFile, setExcelUpdateFile] = useState<File | null>(null);
  const [excelUpdateSheets, setExcelUpdateSheets] = useState<string[]>([]);
  const [excelUpdateSelectedSheet, setExcelUpdateSelectedSheet] = useState("");
  const [excelUpdateLoadingSheets, setExcelUpdateLoadingSheets] = useState(false);
  const [excelPreviewLoading, setExcelPreviewLoading] = useState(false);
  const [excelApplyLoading, setExcelApplyLoading] = useState(false);
  const [excelApplyJob, setExcelApplyJob] = useState<ScenarioOperationJob | null>(null);
  const [excelPreviewData, setExcelPreviewData] = useState<ExcelUpdatePreviewRow[] | null>(null);
  const [excelPreviewWarnings, setExcelPreviewWarnings] = useState<string[]>([]);
  const [excelPreviewNotFound, setExcelPreviewNotFound] = useState(0);
  const [excelPreviewTotalRows, setExcelPreviewTotalRows] = useState(0);
  const [excelSelectedRowIds, setExcelSelectedRowIds] = useState<Set<string>>(new Set());
  const [excelApplyResult, setExcelApplyResult] = useState<{ updated: number; inserted: number; skipped: number } | null>(null);
  const [excelPreviewSearch, setExcelPreviewSearch] = useState("");
  const [excelPreviewPage, setExcelPreviewPage] = useState(1);
  const [excelPreviewPageSize, setExcelPreviewPageSize] = useState<number>(200);
  const [excelExpandedGroupKeys, setExcelExpandedGroupKeys] = useState<Set<string>>(new Set());
  const [isPreviewNarrowViewport, setIsPreviewNarrowViewport] = useState(false);
  const [excelPreviewUploadPhase, setExcelPreviewUploadPhase] = useState<UploadPhase>("idle");
  const [excelPreviewUploadPercent, setExcelPreviewUploadPercent] = useState(0);
  const [excelPreviewUploadStartedAt, setExcelPreviewUploadStartedAt] = useState<number | null>(null);
  const [excelDownloading, setExcelDownloading] = useState(false);
  const [openPermModal, setOpenPermModal] = useState(false);
  const [openMetaModal, setOpenMetaModal] = useState(false);
  const [catalogSuggestions, setCatalogSuggestions] = useState<{
    parameters: string[];
    regions: string[];
    technologies: string[];
    fuels: string[];
    emissions: string[];
    udcs: string[];
  }>({
    parameters: [],
    regions: [],
    technologies: [],
    fuels: [],
    emissions: [],
    udcs: [],
  });
  const [osemosysForm, setOsemosysForm] = useState({
    param_name: "",
    region_name: "",
    technology_name: "",
    fuel_name: "",
    emission_name: "",
    udc_name: "",
    year: "",
    value: "",
  });
  const [permForm, setPermForm] = useState({
    username: "",
    user_identifier: "",
    can_edit_direct: false,
    can_propose: true,
    can_manage_values: false,
  });
  const [scenarioTags, setScenarioTags] = useState<ScenarioTag[]>([]);
  const [metaForm, setMetaForm] = useState<{
    name: string;
    description: string;
    edit_policy: ScenarioEditPolicy;
    simulation_type: SimulationType;
    tag_id: string;
  }>({
    name: "",
    description: "",
    edit_policy: "OWNER_ONLY",
    simulation_type: "NATIONAL",
    tag_id: "",
  });
  // Para valores OSeMOSYS usamos el acceso efectivo calculado por backend.
  // Esto mantiene la semántica de OPEN: cualquier usuario autenticado puede editar valores.
  const canManagePermissions = Boolean(access?.isOwner || access?.can_edit_direct);
  const canManageValues = Boolean(access?.can_manage_values);
  const canEditScenarioMeta = Boolean(access?.isOwner || access?.can_edit_direct);

  useEffect(() => {
    if (!user) return;
    void scenariosApi
      .listScenarioTags()
      .then(setScenarioTags)
      .catch(() => setScenarioTags([]));
  }, [user]);

  const refreshScenarioHeader = useCallback(
    async (scId: number) => {
      const refreshed = await scenariosApi.getScenarioById(scId);
      setScenario(refreshed);
      setParentScenarioName(refreshed.base_scenario_name ?? parentScenarioName);
    },
    [parentScenarioName],
  );

  const refreshCatalogSuggestions = useCallback(
    async (seed?: {
      parameters?: Array<string | null | undefined>;
      regions?: Array<string | null | undefined>;
      technologies?: Array<string | null | undefined>;
      fuels?: Array<string | null | undefined>;
      emissions?: Array<string | null | undefined>;
      udcs?: Array<string | null | undefined>;
    }) => {
      const unique = (items: Array<string | null | undefined>): string[] =>
        Array.from(new Set(items.filter((x): x is string => Boolean(x && x.trim())))).sort((a, b) =>
          a.localeCompare(b, "es"),
        );

      try {
        const [parameters, regions, technologies, fuels, emissions] = await Promise.all([
          catalogsApi.list("parameter", { includeInactive: true, cantidad: 5000 }),
          catalogsApi.list("region", { includeInactive: true, cantidad: 5000 }),
          catalogsApi.list("technology", { includeInactive: true, cantidad: 5000 }),
          catalogsApi.list("fuel", { includeInactive: true, cantidad: 5000 }),
          catalogsApi.list("emission", { includeInactive: true, cantidad: 5000 }),
        ]);
        setCatalogSuggestions({
          parameters: unique([
            ...parameters.map((r) => r.name),
            ...(seed?.parameters ?? []),
          ]),
          regions: unique([
            ...regions.map((r) => r.name),
            ...(seed?.regions ?? []),
          ]),
          technologies: unique([
            ...technologies.map((r) => r.name),
            ...(seed?.technologies ?? []),
          ]),
          fuels: unique([
            ...fuels.map((r) => r.name),
            ...(seed?.fuels ?? []),
          ]),
          emissions: unique([
            ...emissions.map((r) => r.name),
            ...(seed?.emissions ?? []),
          ]),
          udcs: unique(seed?.udcs ?? []),
        });
      } catch {
        setCatalogSuggestions((prev) => ({
          ...prev,
          udcs: unique([...(prev.udcs ?? []), ...(seed?.udcs ?? [])]),
        }));
      }
    },
    [],
  );

  /** Carga una página de valores OSeMOSYS desde el servidor */
  const fetchOsemosysPage = useCallback(
    async (
      scId: number,
      page: number,
      pageSize: number,
      searchTerm: string,
      paramName: string,
      yearValue: string,
    ) => {
      setOsemosysLoading(true);
      try {
        const offset = (page - 1) * pageSize;
        const res = await scenariosApi.listOsemosysValues(scId, {
          offset,
          limit: pageSize,
          ...(searchTerm.trim() ? { search: searchTerm.trim() } : {}),
          ...(paramName.trim() ? { param_name: paramName.trim() } : {}),
          ...(yearValue.trim() ? { year: Number(yearValue) } : {}),
        });
        setOsemosysRows(res.items);
        setOsemosysTotal(res.total);

        await refreshCatalogSuggestions({
          parameters: res.items.map((r) => r.param_name),
          regions: res.items.map((r) => r.region_name),
          technologies: res.items.map((r) => r.technology_name),
          fuels: res.items.map((r) => r.fuel_name),
          emissions: res.items.map((r) => r.emission_name),
          udcs: res.items.map((r) => r.udc_name),
        });
      } catch (err) {
        push(err instanceof Error ? err.message : "Error cargando valores.", "error");
      } finally {
        setOsemosysLoading(false);
      }
    },
    [push, refreshCatalogSuggestions],
  );

  /** Recarga la página actual de valores OSeMOSYS */
  const refreshOsemosysData = useCallback(
    async (scId: number, paramName = filterParamName, yearValue = filterYear) => {
      await Promise.all([
        scenariosApi.listOsemosysSummary(scId).then(setOsemosysSummary),
        fetchOsemosysPage(scId, osemosysPage, osemosysPageSize, osemosysSearch, paramName, yearValue),
      ]);
    },
    [fetchOsemosysPage, filterParamName, filterYear, osemosysPage, osemosysPageSize, osemosysSearch],
  );

  // Carga escenario, permisos, valores OSeMOSYS y solicitudes pendientes al montar
  useEffect(() => {
    if (!Number.isFinite(scenarioId) || !user) return;
    const load = async () => {
      setLoading(true);
      try {
        const sc = await scenariosApi.getScenarioById(scenarioId);
        if (!sc) {
          setScenario(null);
          return;
        }
        setScenario(sc);
          setMetaForm({
            name: sc.name,
            description: sc.description ?? "",
            edit_policy: sc.edit_policy,
            simulation_type: sc.simulation_type,
            tag_id: sc.tag ? String(sc.tag.id) : "",
          });
        setParentScenarioName(sc.base_scenario_name ?? null);

        const myAccess = await scenariosApi.getEffectivePermission(sc, user);
        setAccess(myAccess);

        if (sc.base_scenario_id && !sc.base_scenario_name) {
          try {
            const parent = await scenariosApi.getScenarioById(sc.base_scenario_id);
            setParentScenarioName(parent.name);
          } catch {
            setParentScenarioName(`#${sc.base_scenario_id}`);
          }
        }

        await Promise.all([
          scenariosApi.listOsemosysSummary(sc.id).then(setOsemosysSummary),
          fetchOsemosysPage(sc.id, 1, osemosysPageSize, "", "", ""),
        ]);

        if (myAccess.isOwner || myAccess.can_edit_direct) {
          const [perms, pendingList] = await Promise.all([
            scenariosApi.listPermissions(sc.id),
            scenariosApi.listPendingChangeRequests(sc.id),
          ]);
          setPermissions(perms);
          setPending(pendingList);
        } else {
          setPermissions([]);
          setPending([]);
        }
      } catch (err: unknown) {
        push(err instanceof Error ? err.message : "No se pudo cargar el escenario.", "error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioId, user]);

  // Recarga al cambiar página
  useEffect(() => {
    if (!scenario) return;
    void fetchOsemosysPage(scenario.id, osemosysPage, osemosysPageSize, osemosysSearch, filterParamName, filterYear);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [osemosysPage, osemosysPageSize]);
  function openCreateOsemosys() {
    setEditingOsemosys(null);
    setOsemosysForm({
      param_name: "",
      region_name: "",
      technology_name: "",
      fuel_name: "",
      emission_name: "",
      udc_name: "",
      year: "",
      value: "",
    });
    setOpenOsemosysModal(true);
  }

  function openEditOsemosys(row: OsemosysValueRow) {
    setEditingOsemosys(row);
    setOsemosysForm({
      param_name: row.param_name,
      region_name: row.region_name ?? "",
      technology_name: row.technology_name ?? "",
      fuel_name: row.fuel_name ?? "",
      emission_name: row.emission_name ?? "",
      udc_name: row.udc_name ?? "",
      year: row.year !== null ? String(row.year) : "",
      value: String(row.value),
    });
    setOpenOsemosysModal(true);
  }

  /** Guarda valor OSeMOSYS (crear o actualizar según si estamos editando) */
  async function submitOsemosysValue() {
    if (!scenario || !canManageValues) return;
    if (!osemosysForm.param_name.trim()) {
      push("El parámetro es obligatorio.", "error");
      return;
    }
    const numericValue = Number(osemosysForm.value);
    if (!Number.isFinite(numericValue)) {
      push("El valor debe ser numérico.", "error");
      return;
    }
    const payload = {
      param_name: osemosysForm.param_name.trim(),
      ...(osemosysForm.region_name.trim() ? { region_name: osemosysForm.region_name.trim() } : {}),
      ...(osemosysForm.technology_name.trim()
        ? { technology_name: osemosysForm.technology_name.trim() }
        : {}),
      ...(osemosysForm.fuel_name.trim() ? { fuel_name: osemosysForm.fuel_name.trim() } : {}),
      ...(osemosysForm.emission_name.trim() ? { emission_name: osemosysForm.emission_name.trim() } : {}),
      ...(osemosysForm.udc_name.trim() ? { udc_name: osemosysForm.udc_name.trim() } : {}),
      ...(osemosysForm.year.trim() ? { year: Number(osemosysForm.year) } : {}),
      value: numericValue,
    };
    try {
      if (editingOsemosys) {
        await scenariosApi.updateOsemosysValue(scenario.id, editingOsemosys.id, payload);
      } else {
        await scenariosApi.createOsemosysValue(scenario.id, payload);
      }
      setOpenOsemosysModal(false);
      await refreshOsemosysData(scenario.id);
      await refreshScenarioHeader(scenario.id);
      push("Valor OSeMOSYS guardado.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo guardar el valor OSeMOSYS.", "error");
    }
  }

  async function deactivateOsemosysValue(row: OsemosysValueRow) {
    if (!scenario || !canManageValues) return;
    const confirmed = window.confirm(`Desactivar valor OSeMOSYS '${row.param_name}' (${row.year ?? "sin año"})?`);
    if (!confirmed) return;
    try {
      await scenariosApi.deactivateOsemosysValue(scenario.id, row.id);
      await refreshOsemosysData(scenario.id);
      await refreshScenarioHeader(scenario.id);
      push("Valor OSeMOSYS desactivado.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo desactivar el valor OSeMOSYS.", "error");
    }
  }

  /** Crea solicitud de cambio para un valor; en política OPEN se aplica directo */
  async function submitProposal() {
    if (!scenario || !proposeFor) return;
    const newValue = Number(proposalNewValue);
    if (!Number.isFinite(newValue)) {
      push("El nuevo valor debe ser numérico.", "error");
      return;
    }
    try {
      const created = await scenariosApi.createChangeRequest({
        id_osemosys_param_value: proposeFor.id,
        new_value: newValue,
      });
      if (scenario.edit_policy !== "OPEN" && (access?.isOwner || access?.can_edit_direct)) {
        setPending((prev) => [created, ...prev]);
      } else {
        await refreshOsemosysData(scenario.id);
        await refreshScenarioHeader(scenario.id);
      }
      setProposeFor(null);
      setProposalNewValue("");
      push("Solicitud de cambio creada.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo crear la solicitud.", "error");
    }
  }


  function resetExcelUpdateState() {
    setExcelUpdateFile(null);
    setExcelUpdateSheets([]);
    setExcelUpdateSelectedSheet("");
    setExcelPreviewData(null);
    setExcelPreviewWarnings([]);
    setExcelPreviewNotFound(0);
    setExcelPreviewTotalRows(0);
    setExcelSelectedRowIds(new Set());
    setExcelApplyResult(null);
    setExcelApplyJob(null);
    setExcelPreviewSearch("");
    setExcelPreviewPage(1);
    setExcelPreviewPageSize(200);
    setExcelPreviewUploadPhase("idle");
    setExcelPreviewUploadPercent(0);
    setExcelPreviewUploadStartedAt(null);
  }

  function handleExcelUpdateFileChange(file: File | null) {
    setExcelUpdateFile(file);
    setExcelUpdateSheets([]);
    setExcelUpdateSelectedSheet("");
    setExcelPreviewData(null);
    setExcelApplyResult(null);
    setExcelPreviewPage(1);
    setExcelPreviewUploadPhase("idle");
    setExcelPreviewUploadPercent(0);
    setExcelPreviewUploadStartedAt(null);
  }

  async function loadExcelUpdateSheets() {
    if (!excelUpdateFile) return;
    setExcelUpdateLoadingSheets(true);
    try {
      const res = await officialImportApi.listWorkbookSheets(excelUpdateFile);
      setExcelUpdateSheets(res.sheets);
      if (res.sheets.length >= 1) {
        setExcelUpdateSelectedSheet(res.sheets[0] ?? "");
      }
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudieron leer las hojas del Excel.", "error");
    } finally {
      setExcelUpdateLoadingSheets(false);
    }
  }

  async function handleDownloadExcel(format: "sand" | "raw") {
    if (!scenario) return;
    setExcelDownloading(true);
    try {
      const { blob, filename } = await scenariosApi.downloadScenarioExcel(scenario.id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      push(`Descarga ${format.toUpperCase()} iniciada.`, "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo descargar el Excel.", "error");
    } finally {
      setExcelDownloading(false);
    }
  }

  async function submitExcelPreview() {
    if (!scenario || !excelUpdateFile || !excelUpdateSelectedSheet.trim()) return;
    setExcelPreviewLoading(true);
    setExcelPreviewData(null);
    setExcelApplyResult(null);
    setExcelPreviewPage(1);
    setExcelExpandedGroupKeys(new Set());
    setExcelPreviewUploadPhase("uploading");
    setExcelPreviewUploadPercent(0);
    setExcelPreviewUploadStartedAt(Date.now());
    try {
      const result = await scenariosApi.previewScenarioFromExcel(
        scenario.id,
        { file: excelUpdateFile, sheet_name: excelUpdateSelectedSheet },
        (percent) => {
          setExcelPreviewUploadPercent(percent);
          if (percent >= 100) setExcelPreviewUploadPhase("processing");
        },
      );
      setExcelPreviewData(result.changes);
      setExcelPreviewWarnings(result.warnings);
      setExcelPreviewNotFound(result.not_found);
      setExcelPreviewTotalRows(result.total_rows_read);
      // El backend ya solo devuelve filas con valor distinto; todas son candidatas a aplicar
      const selected = new Set(result.changes.map((ch) => ch.preview_id));
      setExcelSelectedRowIds(selected);
      if (result.changes.length === 0) {
        push("No se detectaron cambios respecto al escenario actual.", "info");
      }
      setExcelPreviewUploadPhase("done");
    } catch (err) {
      setExcelPreviewUploadPhase("error");
      push(err instanceof Error ? err.message : "Error generando preview.", "error");
    } finally {
      setExcelPreviewLoading(false);
    }
  }

  async function submitExcelApply() {
    if (!scenario || !excelPreviewData) return;
    const toApply = excelPreviewData
      .filter((r) => excelSelectedRowIds.has(r.preview_id))
      .map((r) => ({
        preview_id: r.preview_id,
        action: r.action,
        row_id: r.row_id,
        param_name: r.param_name,
        region_name: r.region_name,
        technology_name: r.technology_name,
        fuel_name: r.fuel_name,
        emission_name: r.emission_name,
        timeslice_code: r.timeslice_code,
        mode_of_operation_code: r.mode_of_operation_code,
        season_code: r.season_code,
        daytype_code: r.daytype_code,
        dailytimebracket_code: r.dailytimebracket_code,
        storage_set_code: r.storage_set_code,
        udc_set_code: r.udc_set_code,
        year: r.year,
        new_value: r.new_value,
      }));
    if (toApply.length === 0) {
      push("No hay cambios seleccionados para aplicar.", "info");
      return;
    }
    setExcelApplyLoading(true);
    try {
      const job = await scenariosApi.applyExcelChangesAsync(scenario.id, toApply);
      setExcelApplyJob(job);
      push("Actualización iniciada. Puedes ver el avance en este popup.", "info");
    } catch (err) {
      push(err instanceof Error ? err.message : "Error aplicando cambios.", "error");
      setExcelApplyLoading(false);
    }
  }

  useEffect(() => {
    if (!excelApplyJob) return;
    const isActive = excelApplyJob.status === "QUEUED" || excelApplyJob.status === "RUNNING";
    if (!isActive) return;
    const timer = window.setInterval(() => {
      void scenariosApi
        .getScenarioOperationById(excelApplyJob.id)
        .then(async (job) => {
          setExcelApplyJob(job);
          if (job.status === "SUCCEEDED") {
            const result = job.result_json as { updated?: number; inserted?: number; skipped?: number } | null;
            setExcelApplyResult({
              updated: Number(result?.updated ?? 0),
              inserted: Number(result?.inserted ?? 0),
              skipped: Number(result?.skipped ?? 0),
            });
            setExcelApplyLoading(false);
            if (scenario) {
              await refreshOsemosysData(scenario.id);
              await refreshScenarioHeader(scenario.id);
            }
            push("Actualización completada correctamente.", "success");
          } else if (job.status === "FAILED") {
            setExcelApplyLoading(false);
            push(job.error_message ?? "La actualización asíncrona falló.", "error");
          }
        })
        .catch(() => {
          // No interrumpimos el flujo por errores transitorios de polling.
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [excelApplyJob, push, refreshOsemosysData, refreshScenarioHeader, scenario]);

  useEffect(() => {
    const updateViewportMode = () => {
      setIsPreviewNarrowViewport(window.innerWidth < PREVIEW_NARROW_BREAKPOINT);
    };
    updateViewportMode();
    window.addEventListener("resize", updateViewportMode);
    return () => window.removeEventListener("resize", updateViewportMode);
  }, []);

  const excelPreviewFiltered = useMemo(() => {
    if (!excelPreviewData) return [];
    const term = excelPreviewSearch.trim().toLowerCase();
    if (!term) return excelPreviewData;
    return excelPreviewData.filter((r) =>
      [r.param_name, r.region_name, r.technology_name, r.fuel_name, r.emission_name, r.year?.toString()]
        .filter(Boolean)
        .some((v) => v!.toLowerCase().includes(term)),
    );
  }, [excelPreviewData, excelPreviewSearch]);

  const excelPreviewTotalPages = useMemo(
    () => Math.max(1, Math.ceil(excelPreviewFiltered.length / excelPreviewPageSize)),
    [excelPreviewFiltered.length, excelPreviewPageSize],
  );

  const excelPreviewCurrentPage = Math.min(excelPreviewPage, excelPreviewTotalPages);
  const excelPreviewPageRows = useMemo(() => {
    const start = (excelPreviewCurrentPage - 1) * excelPreviewPageSize;
    return excelPreviewFiltered.slice(start, start + excelPreviewPageSize);
  }, [excelPreviewCurrentPage, excelPreviewPageSize, excelPreviewFiltered]);

  const excelPreviewGroupedPage = useMemo<PreviewGroup[]>(() => {
    const grouped = new Map<string, PreviewGroup>();
    for (const row of excelPreviewPageRows) {
      const key = buildPreviewGroupKey(row);
      const existing = grouped.get(key);
      if (existing) {
        existing.rows.push(row);
      } else {
        grouped.set(key, {
          key,
          param_name: row.param_name,
          region_name: row.region_name,
          technology_name: row.technology_name,
          fuel_name: row.fuel_name,
          emission_name: row.emission_name,
          rows: [row],
        });
      }
    }
    return Array.from(grouped.values());
  }, [excelPreviewPageRows]);

  useEffect(() => {
    if (!excelPreviewGroupedPage.length) {
      setExcelExpandedGroupKeys(new Set());
      return;
    }
    setExcelExpandedGroupKeys((prev) => {
      const next = new Set<string>();
      for (const group of excelPreviewGroupedPage) {
        if (prev.has(group.key)) next.add(group.key);
      }
      if (next.size === 0) {
        for (const group of excelPreviewGroupedPage.slice(0, 8)) {
          next.add(group.key);
        }
      }
      return next;
    });
  }, [excelPreviewGroupedPage]);

  const policyExplanation = useMemo(() => {
    if (!scenario) return "";
    return getPolicyExplanation(scenario.edit_policy);
  }, [scenario]);

  const policyLabel = useMemo(() => {
    if (!scenario) return "";
    if (scenario.edit_policy === "OWNER_ONLY") return "Solo propietario";
    if (scenario.edit_policy === "OPEN") return "Abierta";
    return "Restringida";
  }, [scenario]);

  async function submitScenarioMetadata() {
    if (!scenario || !canEditScenarioMeta) return;
    if (!metaForm.name.trim()) {
      push("El nombre del escenario es obligatorio.", "error");
      return;
    }
    try {
      const updated = await scenariosApi.updateScenario(scenario.id, {
        name: metaForm.name.trim(),
        description: metaForm.description.trim() || null,
        edit_policy: metaForm.edit_policy,
        simulation_type: metaForm.simulation_type,
        tag_id: metaForm.tag_id ? Number(metaForm.tag_id) : null,
      });
      setScenario(updated);
      setMetaForm({
        name: updated.name,
        description: updated.description ?? "",
        edit_policy: updated.edit_policy,
        simulation_type: updated.simulation_type,
        tag_id: updated.tag ? String(updated.tag.id) : "",
      });
      setParentScenarioName(updated.base_scenario_name ?? parentScenarioName);
      setOpenMetaModal(false);
      push("Metadatos del escenario actualizados.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo actualizar el escenario.", "error");
    }
  }

  async function submitPermission() {
    if (!scenario) return;
    const identifier = permForm.user_identifier.trim()
      ? permForm.user_identifier.trim()
      : permForm.username.trim()
        ? `user:${permForm.username.trim()}`
        : "";
    if (!identifier) {
      push("Ingresa el username o el identificador del usuario.", "error");
      return;
    }
    try {
      const permissionPayload = {
        user_identifier: identifier,
        can_edit_direct: permForm.can_edit_direct,
        can_propose: permForm.can_propose,
        can_manage_values: permForm.can_manage_values,
      };
      const upserted = await scenariosApi.upsertPermission(scenario.id, permissionPayload);
      setPermissions((prev) => {
        const exists = prev.some((p) => p.id === upserted.id);
        return exists ? prev.map((p) => (p.id === upserted.id ? upserted : p)) : [upserted, ...prev];
      });
      setOpenPermModal(false);
      push("Permiso actualizado.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo actualizar el permiso.", "error");
    }
  }

  async function reviewRequest(changeRequestId: number, decision: "APPROVED" | "REJECTED") {
    if (!scenario) return;
    try {
      await scenariosApi.reviewChangeRequest(changeRequestId, decision);
      const nextPending = await scenariosApi.listPendingChangeRequests(scenario.id);
      setPending(nextPending);
      await refreshOsemosysData(scenario.id);
      await refreshScenarioHeader(scenario.id);
      push(`Solicitud ${decision === "APPROVED" ? "aprobada" : "rechazada"}.`, "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo procesar la solicitud.", "error");
    }
  }

  // Estados de carga y error antes del render principal
  if (loading) return <section className="pageSection">Cargando escenario...</section>;
  if (!scenario) return <section className="pageSection">Escenario no encontrado.</section>;

  return (
    <section className="pageSection" style={{ display: "grid", gap: 14 }}>
      <div className="toolbarRow">
        <div>
          <h1 style={{ margin: 0 }}>{scenario.name}</h1>
          <p style={{ margin: "6px 0 0", opacity: 0.75 }}>{scenario.description}</p>
          {scenario.tag ? (
            <div style={{ marginTop: 8 }}>
              <ScenarioTagChip tag={scenario.tag} />
            </div>
          ) : null}
          <small style={{ opacity: 0.7 }}>
            Política de edición: <strong>{policyLabel}</strong> · {policyExplanation}
          </small>
        </div>
        {canEditScenarioMeta ? (
          <Button
            variant="ghost"
            onClick={() => {
              setMetaForm({
                name: scenario.name,
                description: scenario.description ?? "",
                edit_policy: scenario.edit_policy,
                simulation_type: scenario.simulation_type,
                tag_id: scenario.tag ? String(scenario.tag.id) : "",
              });
              setOpenMetaModal(true);
            }}
          >
            Editar escenario
          </Button>
        ) : null}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button variant={tab === "values" ? "primary" : "ghost"} onClick={() => setTab("values")}>
          Valores
        </Button>
        <Button
          variant={tab === "permissions" ? "primary" : "ghost"}
          onClick={() => setTab("permissions")}
        >
          Permisos
        </Button>
        <Button variant={tab === "pending" ? "primary" : "ghost"} onClick={() => setTab("pending")}>
          Solicitudes pendientes
        </Button>
      </div>

      {tab === "values" ? (
        <div style={{ display: "grid", gap: 10 }}>
          <div className="toolbarRow">
            <h3 style={{ margin: 0 }}>Valores OSeMOSYS por escenario</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <Button
                variant="ghost"
                onClick={() => void handleDownloadExcel("sand")}
                disabled={excelDownloading}
              >
                {excelDownloading ? "Descargando..." : "Descargar SAND"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => void handleDownloadExcel("raw")}
                disabled={excelDownloading}
              >
                {excelDownloading ? "Descargando..." : "Descargar RAW"}
              </Button>
              {canManageValues ? (
                <>
                  <Button variant="primary" onClick={openCreateOsemosys}>
                    Agregar valor
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      resetExcelUpdateState();
                      setOpenExcelUpdateModal(true);
                    }}
                  >
                    Editar desde Excel
                  </Button>
                </>
              ) : null}
            </div>
          </div>
          <small style={{ opacity: 0.75 }}>
            Estos son los valores base de simulación (`osemosys_param_value`) importados desde Excel.
          </small>
          <small style={{ opacity: 0.7 }}>
            SAND agrupa años por fila; RAW exporta una fila por registro.
          </small>

          <article style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: 14, display: "grid", gap: 8 }}>
            <h4 style={{ margin: 0 }}>Lineage</h4>
            {scenario.base_scenario_id ? (
              <>
                <div style={{ opacity: 0.82 }}>
                  Hijo de <strong>{parentScenarioName ?? scenario.base_scenario_name ?? `#${scenario.base_scenario_id}`}</strong>
                </div>
                <small style={{ opacity: 0.76 }}>
                  Se guarda una referencia simple de los parámetros tocados en este escenario para ayudar a recordar qué cambió.
                </small>
                {scenario.changed_param_names && scenario.changed_param_names.length > 0 ? (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {scenario.changed_param_names.map((paramName) => (
                      <Badge key={paramName} variant="info">
                        {paramName}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, opacity: 0.78 }}>
                    Todavía no hay parámetros marcados como modificados en este escenario derivado.
                  </p>
                )}
              </>
            ) : (
              <p style={{ margin: 0, opacity: 0.78 }}>Este escenario no tiene padre directo.</p>
            )}
          </article>

          {/* Búsqueda global */}
          <div style={{ maxWidth: 500 }}>
            <TextField
              label="Buscar (todas las columnas)"
              value={osemosysSearch}
              placeholder="Parámetro, tecnología, región, año, valor..."
              onChange={(e) => {
                const val = e.target.value;
                setOsemosysSearch(val);
                if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
                searchTimerRef.current = setTimeout(() => {
                  if (!scenario) return;
                  setOsemosysPage(1);
                  void fetchOsemosysPage(scenario.id, 1, osemosysPageSize, val, filterParamName, filterYear);
                }, 400);
              }}
            />
          </div>

          {/* Filtros específicos */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr auto",
              gap: 12,
              alignItems: "end",
              maxWidth: 600,
            }}
          >
            <TextField
              label="Filtrar por parámetro"
              value={filterParamName}
              onChange={(e) => setFilterParamName(e.target.value)}
            />
            <TextField
              label="Filtrar por año"
              type="number"
              value={filterYear}
              onChange={(e) => setFilterYear(e.target.value)}
            />
            <Button
              variant="ghost"
              onClick={() => {
                if (!scenario) return;
                setOsemosysPage(1);
                void fetchOsemosysPage(scenario.id, 1, osemosysPageSize, osemosysSearch, filterParamName, filterYear);
              }}
            >
              Aplicar filtros
            </Button>
          </div>

          {osemosysLoading ? (
            <div style={{ padding: 20, textAlign: "center", opacity: 0.7 }}>Cargando...</div>
          ) : (
            <>
              <div style={{ overflowX: "auto", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead style={{ background: "rgba(255,255,255,0.03)" }}>
                    <tr>
                      {["Parámetro", "Región", "Tecnología", "Combustible", "Emisión", "UDC", "Año", "Valor", "Acciones"].map(
                        (h) => (
                          <th key={h} style={{ textAlign: "left", fontSize: 13, padding: "10px 12px", color: "var(--muted)" }}>
                            {h}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {osemosysRows.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ padding: 14, opacity: 0.75 }}>
                          Sin registros.
                        </td>
                      </tr>
                    ) : (
                      osemosysRows.map((r) => (
                        <tr key={r.id} style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                          <td style={{ padding: "10px 12px" }}>{r.param_name}</td>
                          <td style={{ padding: "10px 12px" }}>{r.region_name ?? "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{r.technology_name ?? "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{r.fuel_name ?? "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{r.emission_name ?? "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{r.udc_name ?? "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{r.year ?? "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{r.value}</td>
                          <td style={{ padding: "10px 12px" }}>
                            {canManageValues ? (
                              <div style={{ display: "flex", gap: 6 }}>
                                <Button variant="ghost" onClick={() => openEditOsemosys(r)}>
                                  Editar
                                </Button>
                                <Button variant="ghost" onClick={() => void deactivateOsemosysValue(r)}>
                                  Desactivar
                                </Button>
                              </div>
                            ) : access?.can_propose ? (
                              <Button variant="ghost" onClick={() => setProposeFor(r)}>
                                Proponer cambio
                              </Button>
                            ) : (
                              <span style={{ opacity: 0.65 }}>Solo lectura</span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Paginación server-side */}
              {(() => {
                const totalPages = Math.max(1, Math.ceil(osemosysTotal / osemosysPageSize));
                return (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <small style={{ opacity: 0.75 }}>
                        Página {osemosysPage} de {totalPages}
                      </small>
                      <small style={{ opacity: 0.75 }}>
                        · {osemosysTotal.toLocaleString()} registros en total
                      </small>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, opacity: 0.85 }}>
                        Por página:
                        <select
                          value={osemosysPageSize}
                          onChange={(e) => {
                            setOsemosysPageSize(Number(e.target.value) || 50);
                            setOsemosysPage(1);
                          }}
                          style={{ padding: "2px 6px", borderRadius: 6, background: "transparent", color: "inherit" }}
                        >
                          {PAGE_SIZE_OPTIONS.map((n) => (
                            <option key={n} value={n}>{n}</option>
                          ))}
                        </select>
                      </label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          className="btn btn--ghost"
                          type="button"
                          disabled={osemosysPage <= 1}
                          onClick={() => setOsemosysPage((p) => Math.max(1, p - 1))}
                        >
                          Anterior
                        </button>
                        <button
                          className="btn btn--ghost"
                          type="button"
                          disabled={osemosysPage >= totalPages}
                          onClick={() => setOsemosysPage((p) => Math.min(totalPages, p + 1))}
                        >
                          Siguiente
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </>
          )}
          <h4 style={{ margin: "6px 0 0 0" }}>Resumen agregado usado por simulación</h4>
          <DataTable
            rows={osemosysSummary}
            rowKey={(r) => `${r.param_name}-${r.year ?? "na"}`}
            columns={[
              { key: "param", header: "Parámetro", render: (r) => r.param_name },
              { key: "year", header: "Año", render: (r) => r.year ?? "—" },
              { key: "records", header: "Registros", render: (r) => r.records },
              { key: "total", header: "Valor total", render: (r) => r.total_value.toFixed(4) },
            ]}
            searchableText={(r) => `${r.param_name} ${r.year ?? ""}`}
          />
        </div>
      ) : null}

      {tab === "permissions" ? (
        <div style={{ display: "grid", gap: 10 }}>
          <div className="toolbarRow">
            <h3 style={{ margin: 0 }}>Permisos del escenario</h3>
            {canManagePermissions ? (
              <Button variant="primary" onClick={() => setOpenPermModal(true)}>
                Agregar / editar permiso
              </Button>
            ) : (
              <small style={{ opacity: 0.75 }}>Visible solo para propietario o administradores del escenario.</small>
            )}
          </div>
          {canManagePermissions ? (
            <DataTable
              rows={permissions}
              rowKey={(r) => String(r.id)}
              columns={[
                {
                  key: "identifier",
                  header: "Usuario",
                  render: (r) => (r.user_identifier.startsWith("user:") ? r.user_identifier.slice(5) : r.user_identifier),
                },
                {
                  key: "edit",
                  header: "Administra",
                  render: (r) => (
                    <Badge variant={r.can_edit_direct ? "success" : "neutral"}>{r.can_edit_direct ? "Sí" : "No"}</Badge>
                  ),
                },
                {
                  key: "prop",
                  header: "Puede proponer",
                  render: (r) => (
                    <Badge variant={r.can_propose ? "success" : "neutral"}>{r.can_propose ? "Sí" : "No"}</Badge>
                  ),
                },
                {
                  key: "manage",
                  header: "Gestiona valores",
                  render: (r) => (
                    <Badge variant={r.can_manage_values ? "success" : "neutral"}>
                      {r.can_manage_values ? "Sí" : "No"}
                    </Badge>
                  ),
                },
              ]}
              searchableText={(r) => `${r.user_identifier}`}
            />
          ) : (
            <p style={{ opacity: 0.8 }}>No tienes permisos para administrar esta sección.</p>
          )}
        </div>
      ) : null}

      {tab === "pending" ? (
        <div style={{ display: "grid", gap: 10 }}>
          <h3 style={{ margin: 0 }}>Solicitudes pendientes</h3>
          <DataTable
            rows={pending}
            rowKey={(r) => String(r.id)}
            columns={[
              { key: "req", header: "Solicitante", render: (r) => r.created_by },
              { key: "change", header: "Cambio", render: (r) => `${r.old_value} → ${r.new_value}` },
              { key: "date", header: "Fecha", render: (r) => new Date(r.created_at).toLocaleString() },
              {
                key: "act",
                header: "Acciones",
                render: (r) =>
                  canManagePermissions ? (
                    <div style={{ display: "flex", gap: 8 }}>
                      <Button variant="primary" onClick={() => reviewRequest(r.id, "APPROVED")}>
                        Aprobar
                      </Button>
                      <Button variant="ghost" onClick={() => reviewRequest(r.id, "REJECTED")}>
                        Rechazar
                      </Button>
                    </div>
                  ) : (
                    <span style={{ opacity: 0.65 }}>Solo propietario / administradores</span>
                  ),
              },
            ]}
            searchableText={(r) => `${r.created_by} ${r.status}`}
          />
        </div>
      ) : null}

      <Modal
        open={openMetaModal}
        title="Editar escenario"
        onClose={() => setOpenMetaModal(false)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setOpenMetaModal(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={() => void submitScenarioMetadata()}>
              Guardar cambios
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 10 }}>
          <TextField label="Nombre" value={metaForm.name} onChange={(e) => setMetaForm((prev) => ({ ...prev, name: e.target.value }))} />
          <TextField label="Descripción" value={metaForm.description} onChange={(e) => setMetaForm((prev) => ({ ...prev, description: e.target.value }))} />
          <label className="field">
            <span className="field__label">Política de edición</span>
            <select
              className="field__input"
              value={metaForm.edit_policy}
              onChange={(e) =>
                setMetaForm((prev) => ({
                  ...prev,
                  edit_policy: e.target.value as ScenarioEditPolicy,
                }))
              }
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
              value={metaForm.simulation_type}
              onChange={(e) =>
                setMetaForm((prev) => ({
                  ...prev,
                  simulation_type: e.target.value as SimulationType,
                }))
              }
            >
              <option value="NATIONAL">Nacional</option>
              <option value="REGIONAL">Regional</option>
            </select>
          </label>
          <small style={{ opacity: 0.75 }}>{getPolicyExplanation(metaForm.edit_policy)}</small>
          <label className="field">
            <span className="field__label">Etiqueta</span>
            <select
              className="field__input"
              value={metaForm.tag_id}
              onChange={(e) => setMetaForm((prev) => ({ ...prev, tag_id: e.target.value }))}
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
        open={openOsemosysModal}
        title={editingOsemosys ? "Editar valor OSeMOSYS" : "Crear valor OSeMOSYS"}
        onClose={() => setOpenOsemosysModal(false)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setOpenOsemosysModal(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={() => void submitOsemosysValue()}>
              Guardar
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 10 }}>
          <TextField
            label="Parámetro"
            value={osemosysForm.param_name}
            list="osemosys-param-suggestions"
            onChange={(e) => setOsemosysForm((p) => ({ ...p, param_name: e.target.value }))}
          />
          <datalist id="osemosys-param-suggestions">
            {catalogSuggestions.parameters.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <TextField
            label="Región (opcional)"
            value={osemosysForm.region_name}
            list="osemosys-region-suggestions"
            onChange={(e) => setOsemosysForm((p) => ({ ...p, region_name: e.target.value }))}
          />
          <datalist id="osemosys-region-suggestions">
            {catalogSuggestions.regions.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <TextField
            label="Tecnología (opcional)"
            value={osemosysForm.technology_name}
            list="osemosys-tech-suggestions"
            onChange={(e) => setOsemosysForm((p) => ({ ...p, technology_name: e.target.value }))}
          />
          <datalist id="osemosys-tech-suggestions">
            {catalogSuggestions.technologies.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <TextField
            label="Combustible (opcional)"
            value={osemosysForm.fuel_name}
            list="osemosys-fuel-suggestions"
            onChange={(e) => setOsemosysForm((p) => ({ ...p, fuel_name: e.target.value }))}
          />
          <datalist id="osemosys-fuel-suggestions">
            {catalogSuggestions.fuels.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <TextField
            label="Emisión (opcional)"
            value={osemosysForm.emission_name}
            list="osemosys-emission-suggestions"
            onChange={(e) => setOsemosysForm((p) => ({ ...p, emission_name: e.target.value }))}
          />
          <datalist id="osemosys-emission-suggestions">
            {catalogSuggestions.emissions.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <TextField
            label="UDC (opcional)"
            value={osemosysForm.udc_name}
            list="osemosys-udc-suggestions"
            onChange={(e) => setOsemosysForm((p) => ({ ...p, udc_name: e.target.value }))}
          />
          <datalist id="osemosys-udc-suggestions">
            {catalogSuggestions.udcs.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <TextField
            label="Año (opcional)"
            type="number"
            value={osemosysForm.year}
            onChange={(e) => setOsemosysForm((p) => ({ ...p, year: e.target.value }))}
          />
          <TextField
            label="Valor"
            type="number"
            value={osemosysForm.value}
            onChange={(e) => setOsemosysForm((p) => ({ ...p, value: e.target.value }))}
          />
        </div>
      </Modal>

      <Modal
        open={openPermModal}
        title="Agregar / editar permiso"
        onClose={() => setOpenPermModal(false)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setOpenPermModal(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={submitPermission}>
              Guardar permiso
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 10 }}>
          <TextField
            label="Username del usuario"
            value={permForm.username}
            onChange={(e) => setPermForm((p) => ({ ...p, username: e.target.value }))}
          />
          <TextField
            label="Identificador (opcional, si no es username)"
            value={permForm.user_identifier}
            onChange={(e) => setPermForm((p) => ({ ...p, user_identifier: e.target.value }))}
          />
          <label>
            <input
              type="checkbox"
              checked={permForm.can_edit_direct}
              onChange={(e) => setPermForm((p) => ({ ...p, can_edit_direct: e.target.checked }))}
            />{" "}
            Administra el escenario
          </label>
          <label>
            <input
              type="checkbox"
              checked={permForm.can_propose}
              onChange={(e) => setPermForm((p) => ({ ...p, can_propose: e.target.checked }))}
            />{" "}
            Puede proponer cambios
          </label>
          <label>
            <input
              type="checkbox"
              checked={permForm.can_manage_values}
              onChange={(e) => setPermForm((p) => ({ ...p, can_manage_values: e.target.checked }))}
            />{" "}
            Gestiona valores
          </label>
        </div>
      </Modal>

      <Modal
        open={Boolean(proposeFor)}
        title="Proponer cambio OSeMOSYS"
        onClose={() => setProposeFor(null)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setProposeFor(null)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={() => void submitProposal()}>
              Crear solicitud
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 10 }}>
          <div style={{ opacity: 0.8 }}>
            Valor actual: <strong>{proposeFor?.value}</strong>
          </div>
          <TextField
            label="Nuevo valor"
            type="number"
            value={proposalNewValue}
            onChange={(e) => setProposalNewValue(e.target.value)}
          />
        </div>
      </Modal>

      <Modal
        open={openExcelUpdateModal}
        title={
          excelApplyResult
            ? "Resultado de actualización"
            : excelPreviewData
              ? "Vista previa de cambios"
              : "Editar escenario desde Excel"
        }
        onClose={() => {
          if (!excelPreviewLoading && !excelApplyLoading) setOpenExcelUpdateModal(false);
        }}
        footer={
          excelApplyResult ? (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <Button variant="primary" onClick={() => setOpenExcelUpdateModal(false)}>
                Cerrar
              </Button>
            </div>
          ) : excelPreviewData ? (
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <Button
                variant="ghost"
                disabled={excelApplyLoading}
                onClick={() => {
                  setExcelPreviewData(null);
                  setExcelSelectedRowIds(new Set());
                  setExcelPreviewSearch("");
                  setExcelExpandedGroupKeys(new Set());
                }}
              >
                Volver
              </Button>
              <div style={{ display: "flex", gap: 8 }}>
                <Button variant="ghost" disabled={excelApplyLoading} onClick={() => setOpenExcelUpdateModal(false)}>
                  Cancelar
                </Button>
                <Button
                  variant="primary"
                  disabled={excelApplyLoading || excelSelectedRowIds.size === 0}
                  onClick={() => void submitExcelApply()}
                >
                  {excelApplyLoading
                    ? "Aplicando..."
                    : `Aplicar ${excelSelectedRowIds.size} cambio${excelSelectedRowIds.size !== 1 ? "s" : ""}`}
                </Button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <Button
                variant="ghost"
                disabled={excelPreviewLoading}
                onClick={() => setOpenExcelUpdateModal(false)}
              >
                Cancelar
              </Button>
              <Button
                variant="primary"
                disabled={excelPreviewLoading || !excelUpdateFile || !excelUpdateSelectedSheet}
                onClick={() => void submitExcelPreview()}
              >
                {excelPreviewLoading ? "Analizando..." : "Vista previa"}
              </Button>
            </div>
          )
        }
      >
        <div style={{ display: "grid", gap: 14 }}>
          {/* ── Carga durante análisis ── */}
          {excelPreviewLoading ? (
            <UploadProgress
              phase={excelPreviewUploadPhase}
              uploadPercent={excelPreviewUploadPercent}
              fileSizeBytes={excelUpdateFile?.size ?? 0}
              startedAt={excelPreviewUploadStartedAt}
            />
          ) : excelApplyResult ? (
            <div
              style={{
                padding: 14,
                borderRadius: 10,
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                display: "grid",
                gap: 6,
                fontSize: 14,
              }}
            >
              <strong>Actualización completada</strong>
              <div>
                Registros actualizados:{" "}
                <strong style={{ color: "var(--success, #4caf50)" }}>{excelApplyResult.updated}</strong>
              </div>
              <div>
                Registros insertados:{" "}
                <strong style={{ color: "var(--success, #4caf50)" }}>{excelApplyResult.inserted}</strong>
              </div>
              {excelApplyResult.skipped > 0 && (
                <div>
                  Omitidos:{" "}
                  <strong style={{ color: "var(--warning, #ff9800)" }}>{excelApplyResult.skipped}</strong>
                </div>
              )}
            </div>
          ) : excelPreviewData ? (
            /* ── Paso 2: Preview con tabla seleccionable ── */
            <>
              {excelApplyLoading && excelApplyJob ? (
                <div
                  style={{
                    padding: 10,
                    borderRadius: 10,
                    border: "1px solid rgba(255,255,255,0.1)",
                    background: "rgba(255,255,255,0.03)",
                    display: "grid",
                    gap: 4,
                    fontSize: 13,
                  }}
                >
                  <strong>Procesando actualización...</strong>
                  <span>
                    Estado: {excelApplyJob.status} · {Math.round(excelApplyJob.progress)}%
                  </span>
                  <span style={{ opacity: 0.85 }}>
                    {excelApplyJob.message ?? excelApplyJob.stage ?? "Aplicando cambios al escenario."}
                  </span>
                </div>
              ) : null}
              <div
                style={{
                  display: "flex",
                  gap: 16,
                  flexWrap: "wrap",
                  fontSize: 13,
                  opacity: 0.85,
                }}
              >
                <span>Filas leídas: <strong>{excelPreviewTotalRows}</strong></span>
                <span>
                  Filas detectadas (update + insert):{" "}
                  <strong style={{ color: "var(--success, #4caf50)" }}>{excelPreviewData.length}</strong>
                </span>
                <span>
                  No encontrados:{" "}
                  <strong style={{ color: excelPreviewNotFound > 0 ? "var(--warning, #ff9800)" : "inherit" }}>
                    {excelPreviewNotFound}
                  </strong>
                </span>
                <span>
                  Seleccionados: <strong>{excelSelectedRowIds.size}</strong> / {excelPreviewData.length}
                </span>
              </div>
              <small style={{ opacity: 0.75 }}>
                Solo se muestran parámetros cuyo valor difiere del actual (se leyeron {excelPreviewTotalRows} filas del Excel).
                {" "}El preview refleja el procesamiento SAND completo (defaults, agregación por timeslice y derivados).
              </small>

              {excelPreviewWarnings.length > 0 && (
                <details>
                  <summary style={{ cursor: "pointer", opacity: 0.85, fontSize: 13 }}>
                    Advertencias ({excelPreviewWarnings.length})
                  </summary>
                  <ul style={{ maxHeight: 150, overflow: "auto", fontSize: 12, margin: "6px 0 0", paddingLeft: 18 }}>
                    {excelPreviewWarnings.map((w, i) => (
                      <li key={i} style={{ opacity: 0.8 }}>{w}</li>
                    ))}
                  </ul>
                </details>
              )}

              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <Button
                  variant="ghost"
                  onClick={() => {
                    const allIds = new Set(excelPreviewData.map((r) => r.preview_id));
                    setExcelSelectedRowIds(allIds);
                  }}
                >
                  Seleccionar todos
                </Button>
                <Button variant="ghost" onClick={() => setExcelSelectedRowIds(new Set())}>
                  Deseleccionar todos
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    const changed = new Set<string>();
                    for (const r of excelPreviewData) {
                      if (r.old_value === null || Math.abs(r.old_value - r.new_value) > 1e-12) {
                        changed.add(r.preview_id);
                      }
                    }
                    setExcelSelectedRowIds(changed);
                  }}
                >
                  Solo con cambios
                </Button>
                <div style={{ marginLeft: "auto", maxWidth: 260 }}>
                  <input
                    type="text"
                    placeholder="Buscar en preview..."
                    value={excelPreviewSearch}
                    onChange={(e) => {
                      setExcelPreviewSearch(e.target.value);
                      setExcelPreviewPage(1);
                    }}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      borderRadius: 8,
                      background: "var(--surface, #1a1a2e)",
                      color: "inherit",
                      border: "1px solid rgba(255,255,255,0.12)",
                      fontSize: 13,
                    }}
                  />
                </div>
              </div>

              <div
                style={{
                  maxHeight: 440,
                  overflowY: "auto",
                  overflowX: isPreviewNarrowViewport ? "auto" : "hidden",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 10,
                  padding: 10,
                }}
              >
                {excelPreviewFiltered.length === 0 ? (
                  <div style={{ padding: 18, opacity: 0.7, textAlign: "center" }}>
                    {excelPreviewSearch.trim() ? "Sin resultados para la búsqueda." : "No hay cambios para mostrar."}
                  </div>
                ) : (
                  <div
                    style={{
                      display: "grid",
                      gap: 10,
                      minWidth: isPreviewNarrowViewport ? 760 : "unset",
                    }}
                  >
                    {excelPreviewGroupedPage.map((group) => {
                      const groupIds = group.rows.map((r) => r.preview_id);
                      const selectedInGroup = groupIds.filter((id) => excelSelectedRowIds.has(id)).length;
                      const allGroupSelected = selectedInGroup > 0 && selectedInGroup === groupIds.length;
                      const expanded = excelExpandedGroupKeys.has(group.key);
                      const hasNewRows = group.rows.some((r) => r.action === "insert");
                      return (
                        <section
                          key={group.key}
                          style={{
                            border: "1px solid rgba(255,255,255,0.08)",
                            borderRadius: 10,
                            background: "rgba(255,255,255,0.02)",
                          }}
                        >
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "auto 1fr auto auto",
                              alignItems: "center",
                              gap: 10,
                              padding: "11px 12px",
                              borderBottom: expanded ? "1px solid rgba(255,255,255,0.06)" : "none",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={allGroupSelected}
                              onChange={(e) => {
                                setExcelSelectedRowIds((prev) => {
                                  const next = new Set(prev);
                                  if (e.target.checked) {
                                    for (const id of groupIds) next.add(id);
                                  } else {
                                    for (const id of groupIds) next.delete(id);
                                  }
                                  return next;
                                });
                              }}
                            />
                            <div style={{ minWidth: 0 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                                <strong>{group.param_name}</strong>
                                {hasNewRows ? (
                                  <span
                                    style={{
                                      fontSize: 11,
                                      padding: "2px 8px",
                                      borderRadius: 999,
                                      border: "1px solid rgba(91, 192, 222, 0.45)",
                                      background: "rgba(91, 192, 222, 0.18)",
                                      color: "#c9f0ff",
                                    }}
                                  >
                                    Nuevo
                                  </span>
                                ) : null}
                              </div>
                              <div style={{ marginTop: 3, fontSize: 12, opacity: 0.82 }}>
                                Región: {group.region_name ?? <span style={{ color: "rgba(255,255,255,0.45)" }}>—</span>}
                                {" · "}
                                Tecnología: {group.technology_name ?? <span style={{ color: "rgba(255,255,255,0.45)" }}>—</span>}
                                {" · "}
                                Combustible: {group.fuel_name ?? <span style={{ color: "rgba(255,255,255,0.45)" }}>—</span>}
                                {" · "}
                                Emisión: {group.emission_name ?? <span style={{ color: "rgba(255,255,255,0.45)" }}>—</span>}
                              </div>
                            </div>
                            <small style={{ opacity: 0.75 }}>
                              {selectedInGroup}/{group.rows.length}
                            </small>
                            <button
                              type="button"
                              className="btn btn--ghost"
                              onClick={() => {
                                setExcelExpandedGroupKeys((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(group.key)) next.delete(group.key);
                                  else next.add(group.key);
                                  return next;
                                });
                              }}
                            >
                              {expanded ? "Ocultar" : "Expandir"}
                            </button>
                          </div>

                          {expanded ? (
                            <div style={{ padding: "8px 12px 12px" }}>
                              <div
                                style={{
                                  display: "grid",
                                  gridTemplateColumns:
                                    "36px minmax(90px, 0.9fr) minmax(120px, 1fr) minmax(120px, 1fr)",
                                  gap: 10,
                                  padding: "7px 4px",
                                  fontSize: 12,
                                  color: "var(--muted)",
                                  borderBottom: "1px solid rgba(255,255,255,0.06)",
                                }}
                              >
                                <span />
                                <strong style={{ textAlign: "right" }}>Año</strong>
                                <strong style={{ textAlign: "right" }}>Valor actual</strong>
                                <strong style={{ textAlign: "right" }}>Nuevo valor</strong>
                              </div>
                              {group.rows.map((r) => {
                                const unchanged = r.old_value !== null && Math.abs(r.old_value - r.new_value) <= 1e-12;
                                const isSelected = excelSelectedRowIds.has(r.preview_id);
                                return (
                                  <div
                                    key={r.preview_id}
                                    style={{
                                      display: "grid",
                                      gridTemplateColumns:
                                        "36px minmax(90px, 0.9fr) minmax(120px, 1fr) minmax(120px, 1fr)",
                                      gap: 10,
                                      alignItems: "center",
                                      padding: "9px 4px",
                                      borderBottom: "1px solid rgba(255,255,255,0.05)",
                                      opacity: unchanged ? 0.55 : isSelected ? 1 : 0.7,
                                      background: isSelected && !unchanged ? "rgba(76,175,80,0.06)" : "transparent",
                                    }}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isSelected}
                                      onChange={() => {
                                        setExcelSelectedRowIds((prev) => {
                                          const next = new Set(prev);
                                          if (next.has(r.preview_id)) next.delete(r.preview_id);
                                          else next.add(r.preview_id);
                                          return next;
                                        });
                                      }}
                                    />
                                    <div style={{ textAlign: "right", fontFamily: "monospace" }}>
                                      {r.year ?? <span style={{ color: "rgba(255,255,255,0.45)" }}>—</span>}
                                    </div>
                                    <div style={{ textAlign: "right", fontFamily: "monospace" }}>
                                      {r.old_value ?? <span style={{ color: "rgba(255,255,255,0.45)" }}>—</span>}
                                    </div>
                                    <div
                                      style={{
                                        textAlign: "right",
                                        fontFamily: "monospace",
                                        fontWeight: unchanged ? 400 : 600,
                                        color: unchanged ? "inherit" : "var(--success, #4caf50)",
                                      }}
                                    >
                                      {r.new_value}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          ) : null}
                        </section>
                      );
                    })}
                  </div>
                )}
              </div>
              {excelPreviewFiltered.length > 0 ? (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <small style={{ opacity: 0.75 }}>
                    Mostrando {(excelPreviewCurrentPage - 1) * excelPreviewPageSize + 1}-
                    {Math.min(excelPreviewCurrentPage * excelPreviewPageSize, excelPreviewFiltered.length)} de{" "}
                    {excelPreviewFiltered.length.toLocaleString()} cambios filtrados
                  </small>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, opacity: 0.85 }}>
                      Filas:
                      <select
                        value={excelPreviewPageSize}
                        onChange={(e) => {
                          setExcelPreviewPageSize(Number(e.target.value) || 200);
                          setExcelPreviewPage(1);
                        }}
                        style={{ padding: "2px 6px", borderRadius: 6, background: "transparent", color: "inherit" }}
                      >
                        {PREVIEW_PAGE_SIZE_OPTIONS.map((size) => (
                          <option key={size} value={size}>
                            {size}
                          </option>
                        ))}
                      </select>
                    </label>
                    <small style={{ opacity: 0.75 }}>
                      Página {excelPreviewCurrentPage} de {excelPreviewTotalPages}
                    </small>
                    <button
                      className="btn btn--ghost"
                      type="button"
                      disabled={excelPreviewCurrentPage <= 1}
                      onClick={() => setExcelPreviewPage((p) => Math.max(1, p - 1))}
                    >
                      Anterior
                    </button>
                    <button
                      className="btn btn--ghost"
                      type="button"
                      disabled={excelPreviewCurrentPage >= excelPreviewTotalPages}
                      onClick={() => setExcelPreviewPage((p) => Math.min(excelPreviewTotalPages, p + 1))}
                    >
                      Siguiente
                    </button>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            /* ── Paso 1: Seleccionar archivo y hoja ── */
            <>
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                  Archivo Excel (.xlsm / .xlsx)
                </label>
                <input
                  type="file"
                  accept=".xlsm,.xlsx,.xls"
                  disabled={excelPreviewLoading}
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null;
                    handleExcelUpdateFileChange(f);
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                <Button
                  variant="ghost"
                  onClick={() => void loadExcelUpdateSheets()}
                  disabled={!excelUpdateFile || excelUpdateLoadingSheets}
                >
                  {excelUpdateLoadingSheets ? "Leyendo hojas..." : "Listar hojas"}
                </Button>
                <small style={{ opacity: 0.75 }}>Para archivos grandes, este paso puede tardar unos segundos.</small>
              </div>

              <label className="field">
                <span className="field__label">Hoja a importar</span>
                <select
                  className="field__input"
                  value={excelUpdateSelectedSheet}
                  disabled={excelPreviewLoading || !excelUpdateSheets.length}
                  onChange={(e) => setExcelUpdateSelectedSheet(e.target.value)}
                >
                  <option value="">{excelUpdateSheets.length ? "Selecciona..." : "Primero lista las hojas"}</option>
                  {excelUpdateSheets.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </label>

              <small style={{ opacity: 0.65 }}>
                Se analizará el archivo y se mostrará una vista previa de los cambios antes de aplicarlos.
                Se podrán aplicar actualizaciones e inserciones de nuevos registros.
                La detección usa paridad total con el procesamiento SAND.
              </small>
            </>
          )}
        </div>
      </Modal>

    </section>
  );
}
