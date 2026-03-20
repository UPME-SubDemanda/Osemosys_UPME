/**
 * Contexto del usuario actual. Expone user, loading y refresh().
 * Debe usarse dentro de CurrentUserProvider. Consumir vía useCurrentUser().
 */
import { createContext } from "react";
import type { User } from "@/types/domain";

export type CurrentUserContextValue = {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

export const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

