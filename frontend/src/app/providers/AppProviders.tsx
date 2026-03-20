/**
 * Composición de todos los providers de la aplicación.
 * Orden: ErrorBoundary (exterior) > Toast > Auth > CurrentUser.
 * El AuthProvider debe envolver CurrentUserProvider porque este depende del token.
 */
import type { ReactNode } from "react";
import { ErrorBoundary } from "@/shared/errors/ErrorBoundary";
import { AuthProvider } from "@/app/providers/AuthProvider";
import { CurrentUserProvider } from "@/app/providers/CurrentUserProvider";
import { ToastProvider } from "@/app/providers/ToastProvider";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AuthProvider>
          <CurrentUserProvider>{children}</CurrentUserProvider>
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}

