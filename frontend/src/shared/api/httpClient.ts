/**
 * Cliente HTTP Axios configurado para la API. Incluye:
 * - baseURL desde env, timeout 30s
 * - Interceptor de request: añade Authorization Bearer si hay token
 * - Interceptor de response: en 401 limpia token y redirige a /login
 */
import axios from "axios";
import { env } from "@/config/env";
import { attachJwtInterceptor } from "@/shared/api/jwtInterceptor";
import { normalizeAxiosError } from "@/shared/errors/normalizeAxiosError";
import { tokenStorage } from "@/shared/storage/tokenStorage";

export const httpClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 30_000,
  headers: {
    Accept: "application/json",
  },
});

attachJwtInterceptor(httpClient);

/** En 401: limpia token y redirige a login para forzar re-autenticación */
httpClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const apiError = normalizeAxiosError(error);
    if (apiError.status === 401) {
      tokenStorage.clear();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(apiError);
  },
);

