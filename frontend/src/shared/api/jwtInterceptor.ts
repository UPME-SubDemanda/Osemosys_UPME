/**
 * Interceptor de request que añade el token JWT como Bearer en el header Authorization.
 * Si no hay token, la petición se envía sin modificar.
 */
import type { AxiosInstance } from "axios";
import { tokenStorage } from "@/shared/storage/tokenStorage";

export function attachJwtInterceptor(client: AxiosInstance) {
  client.interceptors.request.use((config) => {
    /* Añade Bearer token a todas las peticiones salientes */
    const token = tokenStorage.get();
    if (!token) return config;

    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
    return config;
  });
}

