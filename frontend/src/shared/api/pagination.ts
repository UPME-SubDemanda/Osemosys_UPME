/**
 * Tipos de paginación usados por las APIs del backend.
 * PaginatedResponse<T> es el formato estándar de listados paginados.
 */
export type PaginationMeta = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  busqueda: string | null;
};

export type PaginatedResponse<T> = {
  data: T[];
  meta: PaginationMeta;
};

