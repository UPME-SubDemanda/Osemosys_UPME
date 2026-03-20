/**
 * Guard de autenticación. Si el usuario no está autenticado, redirige a /login.
 * Usado como wrapper de rutas que requieren sesión.
 */
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { paths } from "@/routes/paths";

export function RequireAuth() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to={paths.login} replace />;
  }

  return <Outlet />;
}

