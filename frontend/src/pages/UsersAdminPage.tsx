/**
 * UsersAdminPage - Administración de usuarios y permisos
 *
 * Lista usuarios y permite:
 * - Crear nuevos usuarios (email, username, password, permisos)
 * - Toggle de permisos: is_active, can_manage_catalogs, can_import_official_data, can_manage_users
 *
 * Endpoints usados:
 * - usersApi.listUsers()
 * - usersApi.createUser()
 * - usersApi.setPermissions()
 *
 * Los badges son clicables para alternar cada permiso.
 */
import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/app/providers/useToast";
import { usersApi } from "@/features/users/api/usersApi";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { DataTable } from "@/shared/components/DataTable";
import { Modal } from "@/shared/components/Modal";
import { TextField } from "@/shared/components/TextField";
import type { User } from "@/types/domain";

export function UsersAdminPage() {
  const { push } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [openCreate, setOpenCreate] = useState(false);
  const [form, setForm] = useState({
    email: "",
    username: "",
    password: "",
    is_active: true,
    can_manage_catalogs: false,
    can_import_official_data: false,
    can_manage_users: false,
  });

  /** Recarga la lista de usuarios */
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await usersApi.listUsers());
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo cargar usuarios.", "error");
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /** Crea usuario con email, username, password y permisos del formulario */
  async function createUser() {
    if (!form.email.trim() || !form.username.trim() || !form.password.trim()) {
      push("Email, usuario y contraseña son obligatorios.", "error");
      return;
    }
    try {
      await usersApi.createUser({
        email: form.email.trim(),
        username: form.username.trim(),
        password: form.password,
        is_active: form.is_active,
        can_manage_catalogs: form.can_manage_catalogs,
        can_import_official_data: form.can_import_official_data,
        can_manage_users: form.can_manage_users,
      });
      setOpenCreate(false);
      setForm({
        email: "",
        username: "",
        password: "",
        is_active: true,
        can_manage_catalogs: false,
        can_import_official_data: false,
        can_manage_users: false,
      });
      await refresh();
      push("Usuario creado.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudo crear usuario.", "error");
    }
  }

  /** Alterna un permiso del usuario (activo, catálogos, carga oficial, admin usuarios) */
  async function togglePermission(user: User, key: keyof Pick<User, "is_active" | "can_manage_catalogs" | "can_import_official_data" | "can_manage_users">) {
    const payload = {
      is_active: user.is_active,
      can_manage_catalogs: user.can_manage_catalogs,
      can_import_official_data: user.can_import_official_data,
      can_manage_users: user.can_manage_users,
      [key]: !user[key],
    };
    try {
      const updated = await usersApi.setPermissions(user.id, payload);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      push("Permisos actualizados.", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "No se pudieron actualizar permisos.", "error");
    }
  }

  return (
    <section className="pageSection" style={{ display: "grid", gap: 12 }}>
      <div className="toolbarRow">
        <h1 style={{ margin: 0 }}>Usuarios y permisos</h1>
        <Button variant="primary" onClick={() => setOpenCreate(true)}>
          Crear usuario
        </Button>
      </div>
      <small style={{ opacity: 0.8 }}>
        Administra en un solo lugar todos los permisos funcionales (catálogos, carga oficial y administración de usuarios).
      </small>
      {loading ? <p>Cargando usuarios...</p> : null}
      <DataTable
        rows={users}
        rowKey={(r) => r.id}
        columns={[
          { key: "username", header: "Usuario", render: (r) => r.username },
          { key: "email", header: "Email", render: (r) => r.email },
          {
            key: "active",
            header: "Estado",
            render: (r) => (
              <Button variant="ghost" onClick={() => void togglePermission(r, "is_active")}>
                <Badge variant={r.is_active ? "success" : "danger"}>
                  {r.is_active ? "Activo" : "Inactivo"}
                </Badge>
              </Button>
            ),
          },
          {
            key: "catalogs",
            header: "Catálogos",
            render: (r) => (
              <Button variant="ghost" onClick={() => void togglePermission(r, "can_manage_catalogs")}>
                <Badge variant={r.can_manage_catalogs ? "success" : "neutral"}>
                  {r.can_manage_catalogs ? "Sí" : "No"}
                </Badge>
              </Button>
            ),
          },
          {
            key: "official",
            header: "Carga oficial",
            render: (r) => (
              <Button variant="ghost" onClick={() => void togglePermission(r, "can_import_official_data")}>
                <Badge variant={r.can_import_official_data ? "success" : "neutral"}>
                  {r.can_import_official_data ? "Sí" : "No"}
                </Badge>
              </Button>
            ),
          },
          {
            key: "users",
            header: "Admin usuarios",
            render: (r) => (
              <Button variant="ghost" onClick={() => void togglePermission(r, "can_manage_users")}>
                <Badge variant={r.can_manage_users ? "success" : "neutral"}>
                  {r.can_manage_users ? "Sí" : "No"}
                </Badge>
              </Button>
            ),
          },
        ]}
        searchableText={(r) => `${r.username} ${r.email}`}
      />

      <Modal
        open={openCreate}
        title="Crear usuario"
        onClose={() => setOpenCreate(false)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={() => setOpenCreate(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={() => void createUser()}>
              Guardar
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 10 }}>
          <TextField label="Email" value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
          <TextField label="Usuario" value={form.username} onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))} />
          <TextField label="Contraseña" type="password" value={form.password} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))} />
          <label>
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))} /> Activo
          </label>
          <label>
            <input type="checkbox" checked={form.can_manage_catalogs} onChange={(e) => setForm((p) => ({ ...p, can_manage_catalogs: e.target.checked }))} /> Gestiona catálogos
          </label>
          <label>
            <input type="checkbox" checked={form.can_import_official_data} onChange={(e) => setForm((p) => ({ ...p, can_import_official_data: e.target.checked }))} /> Carga oficial
          </label>
          <label>
            <input type="checkbox" checked={form.can_manage_users} onChange={(e) => setForm((p) => ({ ...p, can_manage_users: e.target.checked }))} /> Administra usuarios
          </label>
        </div>
      </Modal>
    </section>
  );
}

