/**
 * Hook para acceder al contexto de autenticación (token, setToken, logout, isAuthenticated).
 * Lanza si se usa fuera de AuthProvider.
 */
import { useContext } from "react";
import { AuthContext } from "@/app/providers/AuthContext";

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth debe usarse dentro de AuthProvider");
  }
  return ctx;
}

