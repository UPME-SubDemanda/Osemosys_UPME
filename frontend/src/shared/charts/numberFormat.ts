/**
 * Helpers de formato numérico para los ejes de las gráficas.
 *
 * `formatAxis3Sig`: garantiza **mínimo 3 cifras significativas** sin notación
 * científica, con separador de miles. Misma lógica que el helper Python
 * `format_axis_3sig` del backend (`chart_service.py`).
 */

/**
 * Formatea un valor con al menos 3 cifras significativas.
 *
 * Reglas:
 *   - |v| ≥ 100             → entero con separador de miles ("1,234")
 *   - 10 ≤ |v| < 100         → 1 decimal ("12.3")
 *   - 1  ≤ |v| < 10          → 2 decimales ("1.23")
 *   - |v| < 1                → suficientes decimales para 3 sig figs
 *                              ("0.123", "0.0123", "0.00123", …)
 *   - 0                      → "0"
 */
export function formatAxis3Sig(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v as number)) return "0";
  const num = Number(v);
  if (num === 0) return "0";
  const absV = Math.abs(num);
  let decimals: number;
  if (absV >= 100) decimals = 0;
  else if (absV >= 10) decimals = 1;
  else if (absV >= 1) decimals = 2;
  else {
    const order = Math.floor(Math.log10(absV)); // negativo
    decimals = Math.min(8, -order + 2);
  }
  return num.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
