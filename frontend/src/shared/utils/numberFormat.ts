const DEFAULT_LOCALE = "es-CO";

export function formatCompactNumber(value: number, maximumFractionDigits = 2): string {
  return value.toLocaleString(DEFAULT_LOCALE, {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  });
}

export function formatPercent(value: number, maximumFractionDigits = 2): string {
  return `${(value * 100).toLocaleString(DEFAULT_LOCALE, {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  })}%`;
}
