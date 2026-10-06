import { httpClient } from "@/shared/api/httpClient";
import type { MosekLicenseStatus } from "@/features/systemSettings/api/mosekLicenseApi";

const path = "/users/me/mosek-license";

async function getPersonalMosekLicense(): Promise<MosekLicenseStatus> {
  const { data } = await httpClient.get<MosekLicenseStatus>(path);
  return data;
}

async function uploadPersonalMosekLicense(file: File): Promise<MosekLicenseStatus> {
  const form = new FormData();
  form.append("license_file", file);
  const { data } = await httpClient.post<MosekLicenseStatus>(path, form);
  return data;
}

async function deletePersonalMosekLicense(): Promise<MosekLicenseStatus> {
  const { data } = await httpClient.delete<MosekLicenseStatus>(path);
  return data;
}

export const personalMosekLicenseApi = {
  get: getPersonalMosekLicense,
  upload: uploadPersonalMosekLicense,
  delete: deletePersonalMosekLicense,
};
