/**
 * API de catálogos (parámetros, regiones, tecnologías, combustibles, emisiones, solvers).
 * CRUD genérico por entidad; soporta listar activos o desactivados.
 */
import { httpClient } from "@/shared/api/httpClient";
import type { PaginatedResponse } from "@/shared/api/pagination";
import type { CatalogEntity, CatalogItem } from "@/types/domain";

/** Mapeo entidad -> endpoint del backend */
const endpointByEntity: Record<CatalogEntity, string> = {
  parameter: "parameters",
  region: "regions",
  technology: "technologies",
  fuel: "fuels",
  emission: "emissions",
  solver: "solvers",
};

type BackendCatalogItem = {
  id: number;
  name: string;
  is_active: boolean;
};

export const catalogsApi = {
  list(entity: CatalogEntity, options?: { includeInactive?: boolean; cantidad?: number }) {
    const endpoint = endpointByEntity[entity];
    const includeInactive = Boolean(options?.includeInactive);
    const cantidad = options?.cantidad ?? 5000;
    const path = `/${endpoint}`;
    return httpClient
      .get<PaginatedResponse<BackendCatalogItem>>(path, {
        params: {
          cantidad,
          offset: 1,
          ...(includeInactive ? { include_inactive: true } : {}),
        },
      })
      .then((r) => r.data.data.map((item) => ({ ...item, entity })));
  },
  create(input: { entity: CatalogEntity; name: string }) {
    const endpoint = endpointByEntity[input.entity];
    return httpClient
      .post<BackendCatalogItem>(`/${endpoint}`, { name: input.name })
      .then((r) => ({ ...r.data, entity: input.entity }));
  },
  update(
    entity: CatalogEntity,
    id: number,
    patch: Pick<CatalogItem, "name"> & { justification?: string },
  ) {
    const endpoint = endpointByEntity[entity];
    return httpClient
      .put<BackendCatalogItem>(`/${endpoint}/${id}`, {
        name: patch.name,
        justification: patch.justification,
      })
      .then((r) => ({ ...r.data, entity }));
  },
  deactivate(entity: CatalogEntity, id: number, justification?: string) {
    const endpoint = endpointByEntity[entity];
    return httpClient.delete(`/${endpoint}/${id}`, { params: { justification } });
  },
};

