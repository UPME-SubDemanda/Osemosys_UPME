/**
 * ProfilePage - Perfil del usuario actual
 *
 * Muestra datos del usuario autenticado: username, email, estado (activo/inactivo)
 * y permisos (catálogos, importación oficial, administración de usuarios).
 *
 * No usa endpoints directos; obtiene datos de useCurrentUser (contexto de auth).
 */
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { Badge } from "@/shared/components/Badge";

export function ProfilePage() {
  const { user, loading } = useCurrentUser();

  return (
    <section className="pageSection">
      <h1 style={{ marginTop: 0 }}>Perfil / Usuario actual</h1>
      {/* Renderizado condicional según estado de carga y autenticación */}
      {loading ? <p>Cargando perfil...</p> : null}
      {!loading && !user ? <p>No hay usuario autenticado.</p> : null}
      {user ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div>
            <strong>Usuario:</strong> {user.username}
          </div>
          <div>
            <strong>Email:</strong> {user.email}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong>Estado:</strong>
            <Badge variant={user.is_active ? "success" : "danger"}>{user.is_active ? "Activo" : "Inactivo"}</Badge>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong>Permiso:</strong>
            <Badge variant={user.can_manage_catalogs ? "success" : "neutral"}>
              {user.can_manage_catalogs ? "Administra catálogos" : "Catálogos (solo lectura)"}
            </Badge>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong>Importación oficial:</strong>
            <Badge variant={user.can_import_official_data ? "success" : "neutral"}>
              {user.can_import_official_data ? "Habilitada" : "No habilitada"}
            </Badge>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong>Admin. usuarios:</strong>
            <Badge variant={user.can_manage_users ? "success" : "neutral"}>
              {user.can_manage_users ? "Habilitada" : "No habilitada"}
            </Badge>
          </div>
        </div>
      ) : null}
    </section>
  );
}

