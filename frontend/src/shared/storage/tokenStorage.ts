/**
 * Almacenamiento del token JWT en localStorage.
 * Incluye expiración (decodificada del JWT o explícita) y evento para sincronizar
 * entre AuthProvider, CurrentUserProvider y otras pestañas.
 */
const TOKEN_KEY = "osemosys.auth.token";
const TOKEN_EXP_KEY = "osemosys.auth.token_exp";
/** Evento disparado al cambiar el token (set/clear); otros listeners pueden refrescar estado */
export const AUTH_TOKEN_CHANGED_EVENT = "osemosys:auth-token-changed";

function notifyTokenChanged(): void {
  try {
    window.dispatchEvent(new Event(AUTH_TOKEN_CHANGED_EVENT));
  } catch {
    // noop
  }
}

/** Lee token; retorna null si no existe o está expirado (y limpia storage) */
function safeRead(): string | null {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const expRaw = localStorage.getItem(TOKEN_EXP_KEY);
    const exp = expRaw ? Number(expRaw) : null;

    if (!token) return null;
    if (exp && Number.isFinite(exp) && Date.now() >= exp) {
      safeRemove();
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

/** Decodifica el claim 'exp' del payload JWT y lo convierte a milisegundos */
function decodeJwtExpMillis(token: string): number | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    const exp = decoded?.exp;
    if (typeof exp === "number" && Number.isFinite(exp)) return exp * 1000;
    return null;
  } catch {
    return null;
  }
}

/** Guarda token y expiración; dispara AUTH_TOKEN_CHANGED_EVENT */
function safeWrite(value: string, explicitExpiryMillis?: number): void {
  try {
    localStorage.setItem(TOKEN_KEY, value);
    const decodedExp = decodeJwtExpMillis(value);
    const expiry = explicitExpiryMillis ?? decodedExp ?? Date.now() + 60 * 60 * 1000;
    localStorage.setItem(TOKEN_EXP_KEY, String(expiry));
  } catch {
    // Si el navegador bloquea storage, degradamos a memoria (AuthProvider).
  }
  notifyTokenChanged();
}

/** Elimina token y expiración; dispara AUTH_TOKEN_CHANGED_EVENT */
function safeRemove(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXP_KEY);
  } catch {
    // noop
  }
  notifyTokenChanged();
}

export const tokenStorage = {
  get: safeRead,
  set: safeWrite,
  clear: safeRemove,
};

