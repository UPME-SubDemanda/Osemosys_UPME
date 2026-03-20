/**
 * Provider de autenticación basado en JWT.
 * Mantiene el token en estado y lo sincroniza con localStorage.
 * Escucha eventos de cambio de token (storage, AUTH_TOKEN_CHANGED_EVENT) para
 * mantener consistencia entre pestañas o cuando el token se actualiza externamente.
 */
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AUTH_TOKEN_CHANGED_EVENT, tokenStorage } from "@/shared/storage/tokenStorage";
import { AuthContext, type AuthContextValue } from "@/app/providers/AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => tokenStorage.get());

  /** Sincroniza estado con localStorage cuando el token cambia en otra pestaña o por logout */
  useEffect(() => {
    const syncFromStorage = () => setTokenState(tokenStorage.get());

    window.addEventListener(AUTH_TOKEN_CHANGED_EVENT, syncFromStorage);
    window.addEventListener("storage", syncFromStorage);
    return () => {
      window.removeEventListener(AUTH_TOKEN_CHANGED_EVENT, syncFromStorage);
      window.removeEventListener("storage", syncFromStorage);
    };
  }, []);

  /** Guarda token en localStorage y actualiza estado; dispara evento para otros listeners */
  const setToken = useCallback((nextToken: string) => {
    tokenStorage.set(nextToken);
    setTokenState(nextToken);
  }, []);

  /** Limpia token de localStorage y estado; dispara evento para refrescar CurrentUser */
  const logout = useCallback(() => {
    tokenStorage.clear();
    setTokenState(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      setToken,
      logout,
    }),
    [logout, setToken, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

