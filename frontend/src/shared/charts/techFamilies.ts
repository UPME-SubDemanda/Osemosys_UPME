/**
 * Familias de tecnología y mapa de colores para gráficas tipo notebook UPME.
 * Equivalente a FAMILIAS_TEC, COLOR_BASE_FAMILIA y COLOR_MAP_PWR del notebook.
 * Incluye conversiones RGB/HLS para generar tonos por tecnología y colores por grupo de combustible.
 */
export const FAMILIAS_TEC: Record<string, string[]> = {
  SOLAR: [
    "PWRSOLRTP",
    "PWRSOLRTP_ZNI",
    "PWRSOLUGE",
    "PWRSOLUGE_BAT",
    "PWRSOLUPE",
  ],
  HIDRO: ["PWRHYDDAM", "PWRHYDROR", "PWRHYDROR_NDC"],
  EOLICA: ["PWRWNDONS", "PWRWNDOFS_FIX", "PWRWNDOFS_FLO"],
  TERMICA_FOSIL: [
    "PWRCOA",
    "PWRCOACCS",
    "PWRNGS_CC",
    "PWRNGS_CS",
    "PWRNGSCCS",
    "PWRDSL",
    "PWRFOIL",
    "PWRJET",
    "PWRLPG",
  ],
  NUCLEAR: ["PWRNUC"],
  BIOMASA_RESIDUOS: ["PWRAFR", "PWRBGS", "PWRWAS"],
  OTRAS: ["PWRCSP", "PWRGEO", "PWRSTD"],
};

const COLOR_BASE_FAMILIA: Record<string, string> = {
  SOLAR: "#FDB813",
  HIDRO: "#1F77B4",
  EOLICA: "#2CA02C",
  TERMICA_FOSIL: "#2B2B2B",
  NUCLEAR: "#7B3F98",
  BIOMASA_RESIDUOS: "#8C6D31",
  OTRAS: "#17BECF",
};

/** Convierte hex a RGB normalizado [0,1] */
function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace(/^#/, "");
  const r = parseInt(clean.slice(0, 2), 16) / 255;
  const g = parseInt(clean.slice(2, 4), 16) / 255;
  const b = parseInt(clean.slice(4, 6), 16) / 255;
  return [r, g, b];
}

/** Convierte RGB a HLS (Hue, Lightness, Saturation) */
function rgbToHls(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = (b - r) / d + 2 / 6;
    else h = (r - g) / d + 4 / 6;
  }
  return [h, l, s];
}

/** Convierte HLS a RGB */
function hlsToRgb(h: number, l: number, s: number): [number, number, number] {
  let r: number, g: number, b: number;
  if (s === 0) {
    r = g = b = l;
  } else {
    const hue2rgb = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1 / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1 / 3);
  }
  return [r, g, b];
}

/** Genera n tonos de un color base (variando luminosidad) */
function generarTonos(colorHex: string, n: number): string[] {
  const [r, g, b] = hexToRgb(colorHex);
  const [h, , s] = rgbToHls(r, g, b);
  const tonos: string[] = [];
  for (let i = 0; i < n; i++) {
    const li = 0.35 + (0.35 * i) / Math.max(1, n - 1);
    const si = s < 0.2 ? s : Math.min(1, s * 1.05);
    const [ri, gi, bi] = hlsToRgb(h, li, si);
    tonos.push(
      "#" +
        [ri, gi, bi]
          .map((x) => Math.round(x * 255).toString(16).padStart(2, "0"))
          .join("")
    );
  }
  return tonos;
}

/** Construye mapa tecnología -> color a partir de familias y colores base */
function construirColorMapPorFamilias(
  familias: Record<string, string[]>,
  coloresBase: Record<string, string>
): Record<string, string> {
  const colorMap: Record<string, string> = {};
  for (const [familia, tecnologias] of Object.entries(familias)) {
    const base = coloresBase[familia] ?? "#888888";
    const tonos = generarTonos(base, tecnologias.length);
    tecnologias.forEach((tech, i) => {
      colorMap[tech] = tonos[i] ?? base;
    });
  }
  return colorMap;
}

/** Mapa tecnología -> color para gráficas (notebook COLOR_MAP_PWR). */
export const COLOR_MAP_PWR = construirColorMapPorFamilias(
  FAMILIAS_TEC,
  COLOR_BASE_FAMILIA
);

const FALLBACK_COLORS = [
  "#94a3b8",
  "#64748b",
  "#475569",
  "#334155",
  "#1e293b",
  "#0f172a",
];

let fallbackIndex = 0;

/**
 * Devuelve el color para una tecnología. Si no está en el mapa (ej. nombres de BD),
 * asigna un color por familia según coincidencia o "OTRAS".
 */
export function getColorForTechnology(techName: string): string {
  const key = techName?.trim() || "N/D";
  if (COLOR_MAP_PWR[key]) return COLOR_MAP_PWR[key];
  const keyUpper = key.toUpperCase();
  for (const [familia, list] of Object.entries(FAMILIAS_TEC)) {
    const idx = list.findIndex(
      (t) => key === t || keyUpper.startsWith(t) || t.startsWith(keyUpper)
    );
    if (idx >= 0) {
      const base = COLOR_BASE_FAMILIA[familia] ?? "#17BECF";
      const tonos = generarTonos(base, list.length);
      return tonos[idx] ?? base;
    }
  }
  const color =
    FALLBACK_COLORS[fallbackIndex % FALLBACK_COLORS.length] ?? "#94a3b8";
  fallbackIndex += 1;
  return color;
}

/** Reinicia el índice de colores fallback (útil entre gráficas). */
export function resetFallbackColors(): void {
  fallbackIndex = 0;
}

// =============================================================================
// Colores por grupo de combustible (notebook COLORES_GRUPOS y asignar_grupo)
// =============================================================================

/** Paleta base por grupo de combustible (notebook COLORES_GRUPOS). REFINERÍAS y RESIDENCIAL. */
export const COLORES_GRUPOS: Record<string, string> = {
  NGS: "#1f77b4",
  JET: "#ff7f0e",
  BGS: "#2ca02c",
  BDL: "#d62728",
  WAS: "#9467bd",
  WOO: "#8c564b",
  GSL: "#e377c2",
  COA: "#7f7f7f",
  ELC: "#bcbd22",
  BAG: "#bcc2c3",
  DSL: "#aec7e8",
  LPG: "#ffbb78",
  FOL: "#98df8a",
  AUT: "#ff9896",
  OIL: "#000000",
  PHEV: "#c5b0d5",
  HEV: "#f7b6d2",
};

/**
 * Asigna un grupo de combustible a partir de un nombre (ej. TECHNOLOGY_FUEL).
 * Orden de chequeo igual que en el notebook.
 */
export function asignarGrupo(nombre: string): string {
  const n = (nombre ?? "").toUpperCase();
  if (n.includes("NGS")) return "NGS";
  if (n.includes("JET")) return "JET";
  if (n.includes("BGS")) return "BGS";
  if (n.includes("BDL")) return "BDL";
  if (n.includes("WAS")) return "WAS";
  if (n.includes("WOO")) return "WOO";
  if (n.includes("GSL")) return "GSL";
  if (n.includes("COA")) return "COA";
  if (n.includes("ELC")) return "ELC";
  if (n.includes("BAG")) return "BAG";
  if (n.includes("DSL")) return "DSL";
  if (n.includes("LPG")) return "LPG";
  if (n.includes("FOL")) return "FOL";
  if (n.includes("AUT")) return "AUT";
  if (n.includes("OIL")) return "OIL";
  if (n.includes("PHEV") || n.includes("APHEV")) return "PHEV";
  if (n.includes("HEV") || n.includes("AHEV")) return "HEV";
  return nombre?.trim() || "OTRO";
}

/** Devuelve el color para un grupo de combustible (REFINERÍAS). */
export function getColorForFuelGroup(group: string): string {
  return COLORES_GRUPOS[group] ?? "#333333";
}
