import { httpClient } from "@/shared/api/httpClient";

export type MosekLicenseStatus = {
  configured: boolean;
  updated_at: string | null;
};

const path = "/admin/system-settings/mosek-license";

async function getGlobalMosekLicense(): Promise<MosekLicenseStatus> {
  const { data } = await httpClient.get<MosekLicenseStatus>(path);
  return data;
}

async function uploadGlobalMosekLicense(file: File): Promise<MosekLicenseStatus> {
  const form = new FormData();
  form.append("license_file", file);
  const { data } = await httpClient.post<MosekLicenseStatus>(path, form);
  return data;
}

async function deleteGlobalMosekLicense(): Promise<MosekLicenseStatus> {
  const { data } = await httpClient.delete<MosekLicenseStatus>(path);
  return data;
}

export const mosekLicenseApi = {
  getGlobal: getGlobalMosekLicense,
  uploadGlobal: uploadGlobalMosekLicense,
  deleteGlobal: deleteGlobalMosekLicense,
};
