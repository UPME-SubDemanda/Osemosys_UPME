/**
 * Guard de permisos: requiere can_import_official_data. Redirige a escenarios si no tiene permiso.
 */
import { Navigate, Outlet } from "react-router-dom";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { paths } from "@/routes/paths";

export function RequireOfficialDataImporter() {
  const { user, loading } = useCurrentUser();

  if (loading) return <section className="pageSection">Cargando permisos...</section>;
  if (!user?.can_import_official_data) {
    return <Navigate to={paths.scenarios} replace />;
  }
  return <Outlet />;
}
