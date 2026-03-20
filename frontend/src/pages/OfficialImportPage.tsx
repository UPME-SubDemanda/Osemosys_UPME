/**
 * OfficialImportPage - Importación de datos oficiales desde Excel
 *
 * Permite subir archivos .xlsm/.xlsx, seleccionar una hoja y cargar datos a la base.
 * Muestra barra de progreso durante la subida (UploadProgress).
 * El sistema valida tipos, corrige formatos y omite filas inválidas con advertencias.
 *
 * Endpoints usados:
 * - officialImportApi.listWorkbookSheets(file)
 * - officialImportApi.uploadWorkbook(file, sheet, onProgress, onDone)
 *
 * Resultado incluye: inserted, updated, skipped, warnings, notebook_preprocess.
 */
import { useCallback, useMemo, useState } from "react";
import { useToast } from "@/app/providers/useToast";
import { officialImportApi, type OfficialImportResult } from "@/features/officialImport/api/officialImportApi";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { UploadProgress, type UploadPhase } from "@/shared/components/UploadProgress";
import styles from "./OfficialImportPage.module.css";

export function OfficialImportPage() {
  const { push } = useToast();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [availableSheets, setAvailableSheets] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [loadingSheets, setLoadingSheets] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OfficialImportResult | null>(null);

  const [uploadPhase, setUploadPhase] = useState<UploadPhase>("idle");
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadStartedAt, setUploadStartedAt] = useState<number | null>(null);

  // Habilitar botón solo si hay archivo, hoja seleccionada y no está cargando
  const canSubmit = useMemo(
    () => Boolean(selectedFile) && Boolean(selectedSheet) && !loading && !loadingSheets,
    [loading, loadingSheets, selectedFile, selectedSheet],
  );

  /** Lee las hojas del archivo Excel; se llama al seleccionar archivo */
  async function loadSheets(file: File) {
    setLoadingSheets(true);
    setAvailableSheets([]);
    setSelectedSheet("");
    setResult(null);
    try {
      const res = await officialImportApi.listWorkbookSheets(file);
      setAvailableSheets(res.sheets);
      if (res.sheets.length === 1) {
        setSelectedSheet(res.sheets[0] ?? "");
      }
      push("Selecciona la hoja a importar.", "success");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "message" in err && typeof err.message === "string"
          ? err.message
          : "No se pudieron leer las hojas del archivo.";
      push(message, "error");
    } finally {
      setLoadingSheets(false);
    }
  }

  const handleUploadProgress = useCallback((percent: number) => {
    setUploadPercent(percent);
    if (percent >= 100) {
      setUploadPhase("processing");
    }
  }, []);

  const handleUploadDone = useCallback(() => {
    setUploadPhase("processing");
  }, []);

  /** Ejecuta la importación; muestra UploadProgress durante la subida */
  async function onImport() {
    if (!selectedFile) {
      push("Selecciona un archivo .xlsm o .xlsx.", "error");
      return;
    }
    if (!selectedSheet) {
      push("Selecciona primero la hoja del Excel a importar.", "error");
      return;
    }
    setLoading(true);
    setResult(null);
    setUploadPhase("uploading");
    setUploadPercent(0);
    setUploadStartedAt(Date.now());
    try {
      const res = await officialImportApi.uploadWorkbook(
        selectedFile,
        selectedSheet,
        handleUploadProgress,
        handleUploadDone,
      );
      setUploadPhase("done");
      setResult(res);
      if (res.inserted + res.updated === 0) {
        push("El archivo se procesó, pero no se cargaron registros. Revisa el formato de hojas/columnas.", "error");
      } else {
        push("Importación finalizada.", "success");
      }
    } catch (err) {
      setUploadPhase("error");
      const message =
        typeof err === "object" && err !== null && "message" in err && typeof err.message === "string"
          ? err.message
          : "No se pudo importar el archivo.";
      push(message, "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={`pageSection ${styles.section}`}>
      <div>
        <h1 className={styles.headerTitle}>Importación oficial de datos</h1>
        <p className={styles.headerDesc}>
          Sube el archivo oficial en Excel. El sistema valida tipos, corrige formatos comunes y omite filas inválidas
          con advertencias.
          La importación de hojas grandes puede tardar varios minutos.
        </p>
      </div>

      <div className={styles.formWrap}>
        <label className="field">
          <span className="field__label">Archivo Excel (.xlsm / .xlsx)</span>
          <input
            id="official-import-file"
            className="field__input"
            type="file"
            accept=".xlsm,.xlsx"
            aria-label="Seleccionar archivo Excel"
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              setSelectedFile(file);
              if (file) {
                void loadSheets(file);
              } else {
                setAvailableSheets([]);
                setSelectedSheet("");
              }
            }}
            disabled={loading || loadingSheets}
          />
        </label>
        <label className="field">
          <span className="field__label">Hoja a importar</span>
          <select
            id="sheet-select"
            className="field__input"
            value={selectedSheet}
            onChange={(e) => setSelectedSheet(e.target.value)}
            disabled={loading || loadingSheets || availableSheets.length === 0}
          >
            <option value="">{loadingSheets ? "Leyendo hojas..." : "Selecciona una hoja..."}</option>
            {availableSheets.map((sheet) => (
              <option key={sheet} value={sheet}>
                {sheet}
              </option>
            ))}
          </select>
        </label>
        <div className={styles.actionsRow}>
          <Button variant="primary" onClick={onImport} disabled={!canSubmit}>
            {loading ? "Procesando..." : "Cargar datos a la base"}
          </Button>
          {loadingSheets ? <Badge variant="neutral">Leyendo hojas del archivo...</Badge> : null}
        </div>

        {uploadPhase !== "idle" ? (
          <UploadProgress
            phase={uploadPhase}
            uploadPercent={uploadPercent}
            fileSizeBytes={selectedFile?.size ?? 0}
            startedAt={uploadStartedAt}
          />
        ) : null}
      </div>

      {result ? (
        <div className={styles.resultBox}>
          <h3 className={styles.resultTitle}>Resultado</h3>
          <div>
            <strong>Archivo:</strong> {result.filename}
          </div>
          <div>
            <strong>Importado por:</strong> {result.imported_by}
          </div>
          <div>
            <strong>Filas leídas:</strong> {result.total_rows_read}
          </div>
          <div>
            <strong>Insertadas:</strong> {result.inserted} · <strong>Actualizadas:</strong> {result.updated} ·{" "}
            <strong>Omitidas:</strong> {result.skipped}
          </div>
          <div>
            <strong>Advertencias:</strong> {result.warnings.length}
          </div>
          {result.notebook_preprocess ? (
            <div className={styles.preprocessOk}>
              <strong>Preprocesamiento tipo notebook:</strong> aplicado correctamente
              {Object.keys(result.notebook_preprocess).length > 0 ? (
                <span className={styles.preprocessStats}>
                  {" "}
                  ({Object.entries(result.notebook_preprocess)
                    .filter(([, v]) => v != null && v !== 0)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(", ")})
                </span>
              ) : null}
            </div>
          ) : result.notebook_preprocess_error ? (
            <div className={styles.preprocessError} role="alert">
              <strong>Preprocesamiento tipo notebook:</strong> no aplicado — {result.notebook_preprocess_error}
            </div>
          ) : null}
          {result.warnings.length ? (
            <div className={styles.warningsBox}>
              {result.warnings.slice(0, 30).map((warning, idx) => (
                <div key={`${warning}-${idx}`} className={styles.warningItem}>
                  - {warning}
                </div>
              ))}
              {result.warnings.length > 30 ? (
                <div className={styles.warningMore}>
                  ... y {result.warnings.length - 30} advertencias adicionales.
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
