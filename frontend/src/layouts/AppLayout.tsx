/**
 * Layout principal de la aplicación autenticada.
 * Incluye sidebar con navegación (según permisos del usuario), header con info de sesión
 * y botón de cerrar sesión, y área principal donde se renderizan las rutas hijas.
 */
import { NavLink, Outlet } from "react-router-dom";
import { paths } from "@/routes/paths";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { Button } from "@/shared/components/Button";
import { useCurrentUser } from "@/app/providers/useCurrentUser";

export function AppLayout() {
  const { logout } = useAuth();
  const { user } = useCurrentUser();

  /** Items del menú visibles globalmente; módulos sensibles quedan fuera del sidebar. */
  const navItems = [
    { to: paths.app, label: "Inicio" },
    { to: paths.scenarios, label: "Escenarios" },
    { to: paths.changeRequests, label: "Solicitudes de cambio" },
    ...(user?.can_manage_catalogs ? [{ to: paths.catalogs, label: "Catálogos" }] : []),
    ...(user?.can_manage_users ? [{ to: paths.usersAdmin, label: "Usuarios y permisos" }] : []),
    { to: paths.simulation, label: "Simulación" },
    { to: paths.results, label: "Resultados" },
    { to: paths.profile, label: "Perfil" },
  ];

  return (
    <div className="appShell">
      <aside className="appSidebar">
        <div style={{ padding: "18px 16px 10px", borderBottom: "1px solid rgba(255,255,255,0.08)", flexShrink: 0 }}>
          <h2 style={{ margin: 0, fontSize: 17 }}>OSeMOSYS UI</h2>
          <p style={{ margin: "6px 0 0", fontSize: 12, opacity: 0.75 }}>Planeación y simulación energética</p>
        </div>
        <nav className="appSidebarNav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === paths.app}
              className={({ isActive }) => (isActive ? "sidebarLink sidebarLink--active" : "sidebarLink")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <section style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
      <header
        className="appTopHeader"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 20px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          background: "rgb(11, 18, 32)",
          position: "sticky",
          top: 0,
          zIndex: 100,
          boxShadow: "0 1px 0 rgba(0, 0, 0, 0.35)",
        }}
      >
        <div>
          <div style={{ fontWeight: 700 }}>Sistema de escenarios OSeMOSYS</div>
          <small style={{ opacity: 0.75 }}>
            {user ? `${user.username} · ${user.email}` : "Sin sesión"}
          </small>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Button variant="ghost" onClick={logout}>
            Cerrar sesión
          </Button>
        </div>
      </header>

      <main className="appMainOutlet" style={{ padding: 20 }}>
        <Outlet />
      </main>
      </section>
    </div>
  );
}
