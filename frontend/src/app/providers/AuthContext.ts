/**
 * Contexto de autenticación. Expone token, estado isAuthenticated, setToken y logout.
 * Debe usarse dentro de AuthProvider. Consumir vía useAuth().
 */
import { createContext } from "react";

export type AuthContextValue = {
  token: string | null;
  isAuthenticated: boolean;
  setToken: (token: string) => void;
  logout: () => void;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

