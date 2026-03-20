/**
 * Hook para acceder al usuario actual y sus permisos.
 * Lanza si se usa fuera de CurrentUserProvider.
 */
import { useContext } from "react";
import { CurrentUserContext } from "@/app/providers/CurrentUserContext";

export function useCurrentUser() {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) throw new Error("useCurrentUser debe usarse dentro de CurrentUserProvider.");
  return ctx;
}

