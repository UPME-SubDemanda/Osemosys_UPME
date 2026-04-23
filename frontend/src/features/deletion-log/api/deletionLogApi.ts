/** Cliente HTTP para la bitácora de eliminaciones. */
import { httpClient } from "@/shared/api/httpClient";
import type { PaginatedResponse } from "@/shared/api/pagination";
import type { DeletionLogEntry } from "@/types/domain";

export const deletionLogApi = {
  async list(params: {
    entity_type?: "SCENARIO" | "SIMULATION_JOB";
    username?: string;
    from_date?: string;
    to_date?: string;
    cantidad?: number;
    offset?: number;
  } = {}) {
    const { data } = await httpClient.get<PaginatedResponse<DeletionLogEntry>>(
      "/deletion-log",
      { params },
    );
    return data;
  },
};
