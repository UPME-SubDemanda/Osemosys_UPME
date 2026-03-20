/**
 * Tipo de error normalizado para la UI. Evita acoplar el resto de la app a AxiosError.
 * Incluye message, status HTTP, code opcional del backend y details para troubleshooting.
 */
export type ApiError = {
  name: "ApiError";
  message: string;
  status?: number;
  /**
   * Idealmente un código estable del backend (p.ej. "invalid_credentials").
   */
  code?: string;
  /**
   * Datos crudos para troubleshooting (no mostrar al usuario final).
   */
  details?: unknown;
};

/** Type guard para verificar si un valor es ApiError */
export function isApiError(value: unknown): value is ApiError {
  return Boolean(value) && typeof value === "object" && (value as ApiError).name === "ApiError";
}

/** Crea un ApiError a partir de sus campos (name se añade automáticamente) */
export function createApiError(input: Omit<ApiError, "name">): ApiError {
  return { name: "ApiError", ...input };
}

