import type { SandExportVerification } from "@/features/scenarios/api/scenariosApi";

function shortSandFileName(name: string, maxLen = 42): string {
  if (name.length <= maxLen) return name;
  return `${name.slice(0, maxLen - 2)}…`;
}

type Props = {
  data: SandExportVerification;
  variant: "concatenate" | "standalone";
};

/**
 * Resultado de la doble verificación de un Excel integrado (vs base y archivos nuevos).
 */
export function SandExportVerificationPanel({ data, variant }: Props) {
  const ev = data;
  const isStandalone = variant === "standalone";

  return (
    <div
      style={{
        padding: 12,
        borderRadius: 10,
        border: "1px solid rgba(255,255,255,0.12)",
        background: "rgba(255,255,255,0.04)",
        display: "grid",
        gap: 10,
        fontSize: 13,
      }}
    >
      <strong style={{ fontSize: 14 }}>Validación del Excel integrado</strong>
      {ev.verification_error ? (
        <p style={{ margin: 0, color: "var(--warning, #ff9800)" }}>
          No se pudo releer el exportado: {ev.verification_error}
        </p>
      ) : null}

      {!isStandalone && !ev.applies_to_download && !ev.verification_error ? (
        <p style={{ margin: 0, opacity: 0.9 }}>
          Hay conflictos entre archivos nuevos: el ZIP descargado no incluye el Excel integrado. La tabla siguiente
          valida el archivo generado en el servidor (no coincide con el archivo de esta descarga).
        </p>
      ) : null}

      {isStandalone && ev.ok && !ev.verification_error ? (
        <p style={{ margin: 0, opacity: 0.92, color: "var(--success, #4caf50)" }}>
          El archivo integrado que subiste coincide con los cambios esperados: se releyó el Excel y se comprobaron
          filas nuevas y celdas modificadas frente a la base y los archivos nuevos.
        </p>
      ) : null}

      {!isStandalone && ev.applies_to_download && ev.ok ? (
        <p style={{ margin: 0, opacity: 0.92, color: "var(--success, #4caf50)" }}>
          El archivo descargado se verificó releyendo el Excel exportado: las filas nuevas y las celdas modificadas
          esperadas coinciden con el integrado.
        </p>
      ) : null}

      {!isStandalone && ev.applies_to_download && !ev.ok && !ev.verification_error ? (
        <p style={{ margin: 0, color: "var(--warning, #ff9800)" }}>
          Advertencia: hay {ev.total_faltantes.toLocaleString()} discrepancia(s) entre el exportado y los cambios
          esperados. Revisa la muestra o el informe integracion_sand_log.txt.
        </p>
      ) : null}

      {isStandalone && !ev.ok && !ev.verification_error ? (
        <p style={{ margin: 0, color: "var(--warning, #ff9800)" }}>
          Advertencia: hay {ev.total_faltantes.toLocaleString()} discrepancia(s) entre el archivo integrado y los
          cambios esperados respecto a la base y los archivos nuevos.
        </p>
      ) : null}

      {!isStandalone && !ev.applies_to_download && ev.ok && !ev.verification_error ? (
        <p style={{ margin: 0, opacity: 0.88 }}>
          Validación interna correcta sobre el integrado generado (no incluido en el ZIP por conflictos).
        </p>
      ) : null}

      {!isStandalone && !ev.applies_to_download && !ev.ok && !ev.verification_error ? (
        <p style={{ margin: 0, color: "var(--warning, #ff9800)" }}>
          Validación interna: hay discrepancias en el archivo generado en servidor. Revisa conflictos y el log.
        </p>
      ) : null}

      {ev.per_file.length > 0 ? (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
            }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.12)", textAlign: "left" }}>
                <th style={{ padding: "6px 8px 6px 0" }}>Archivo</th>
                <th style={{ padding: "6px 8px", textAlign: "right" }}>Nuevas</th>
                <th style={{ padding: "6px 8px", textAlign: "right" }}>Modif.</th>
                <th style={{ padding: "6px 8px", textAlign: "right" }}>Omit.</th>
                <th style={{ padding: "6px 8px", textAlign: "right" }}>Falta</th>
                <th style={{ padding: "6px 0 6px 8px" }}>Estado</th>
              </tr>
            </thead>
            <tbody>
              {ev.per_file.map((row) => (
                <tr key={row.archivo} style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                  <td style={{ padding: "6px 8px 6px 0", wordBreak: "break-word" }}>
                    {shortSandFileName(row.archivo)}
                  </td>
                  <td style={{ padding: "6px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {row.n_verificadas_nuevas.toLocaleString()}
                  </td>
                  <td style={{ padding: "6px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {row.n_verificadas_modif.toLocaleString()}
                  </td>
                  <td style={{ padding: "6px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {row.n_omitidas_drop.toLocaleString()}
                  </td>
                  <td style={{ padding: "6px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {row.n_faltantes.toLocaleString()}
                  </td>
                  <td style={{ padding: "6px 0 6px 8px" }}>{row.ok ? "OK" : "Falla"}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr style={{ fontWeight: 600 }}>
                <td style={{ padding: "8px 8px 0 0" }}>Total</td>
                <td style={{ padding: "8px 8px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {ev.total_nuevas_verificadas.toLocaleString()}
                </td>
                <td style={{ padding: "8px 8px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {ev.total_modificadas_verificadas.toLocaleString()}
                </td>
                <td style={{ padding: "8px 8px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {ev.total_omitidas_drop.toLocaleString()}
                </td>
                <td style={{ padding: "8px 8px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {ev.total_faltantes.toLocaleString()}
                </td>
                <td style={{ padding: "8px 0 0 8px" }} />
              </tr>
            </tfoot>
          </table>
        </div>
      ) : null}

      {ev.faltantes_muestra && ev.faltantes_muestra.length > 0 ? (
        <div style={{ display: "grid", gap: 6 }}>
          <span style={{ opacity: 0.85, fontSize: 12 }}>Muestra de discrepancias (primeras filas):</span>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, opacity: 0.92 }}>
            {ev.faltantes_muestra.map((f, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {String(f.tipo ?? "")} · {String(f.Parameter ?? "")} · tech={String(f.TECHNOLOGY ?? "")} · col=
                {String(f.columna ?? "")} · esperado={String(f.valor_esperado ?? "")} · actual=
                {String(f.valor_actual ?? "")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
