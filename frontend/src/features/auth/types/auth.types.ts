/**
 * Tipos para autenticación OAuth2 compatible con FastAPI.
 */

/** Payload para login (username + password) */
export type LoginRequest = {
  username: string;
  password: string;
};

/**
 * Respuesta típica de FastAPI OAuth2PasswordBearer.
 * POST /auth/login => { access_token, token_type }
 */
export type LoginResponse = {
  access_token: string;
  token_type: "bearer" | string;
};

