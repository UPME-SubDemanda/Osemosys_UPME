/**
 * API de autenticación. Login vía OAuth2 (form-urlencoded) compatible con FastAPI.
 * Retorna access_token para usar como Bearer en peticiones subsiguientes.
 */
import { httpClient } from "@/shared/api/httpClient";
import type { LoginRequest, LoginResponse } from "@/features/auth/types/auth.types";

/**
 * Envía credenciales como application/x-www-form-urlencoded (OAuth2PasswordRequestForm).
 * El baseURL de httpClient ya incluye el prefijo versionado (ej. /api/v1).
 */
async function login(payload: LoginRequest): Promise<LoginResponse> {
  const body = new URLSearchParams();
  body.set("username", payload.username);
  body.set("password", payload.password);

  const { data } = await httpClient.post<LoginResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export const authApi = { login };

