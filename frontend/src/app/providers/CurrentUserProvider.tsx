/**
 * Provider del usuario actual. Obtiene /users/me cuando hay token y refresca
 * al cambiar el token (login, logout, otra pestaña). Si la respuesta es 401,
 * limpia el token para forzar re-login.
 */
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AUTH_TOKEN_CHANGED_EVENT, tokenStorage } from "@/shared/storage/tokenStorage";
import { CurrentUserContext } from "@/app/providers/CurrentUserContext";
import type { User } from "@/types/domain";
import { usersApi } from "@/features/users/api/usersApi";
import { normalizeAxiosError } from "@/shared/errors/normalizeAxiosError";

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  /** Llama a /users/me; si no hay token o 401, limpia y pone user=null */
  const refresh = useCallback(async () => {
    const token = tokenStorage.get();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await usersApi.getMe();
      setUser(me);
    } catch (err) {
      const apiError = normalizeAxiosError(err);
      if (apiError.status === 401) {
        tokenStorage.clear();
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  /** Refresca al montar (y cuando cambia refresh) */
  useEffect(() => {
    void refresh();
  }, [refresh]);

  /** Refresca cuando el token cambia (login/logout en esta u otra pestaña) */
  useEffect(() => {
    const onToken = () => void refresh();
    window.addEventListener(AUTH_TOKEN_CHANGED_EVENT, onToken);
    return () => window.removeEventListener(AUTH_TOKEN_CHANGED_EVENT, onToken);
  }, [refresh]);

  const value = useMemo(() => ({ user, loading, refresh }), [loading, refresh, user]);
  return <CurrentUserContext.Provider value={value}>{children}</CurrentUserContext.Provider>;
}

