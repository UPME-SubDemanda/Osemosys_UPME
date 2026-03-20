import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "@/features/auth/api/authApi";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { paths } from "@/routes/paths";
import { Button } from "@/shared/components/Button";
import { TextField } from "@/shared/components/TextField";
import { normalizeAxiosError } from "@/shared/errors/normalizeAxiosError";
import { useCurrentUser } from "@/app/providers/useCurrentUser";

/** Icono de usuario que hereda el color del contenedor (colores de la app). */
function UserIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
    </svg>
  );
}

type FieldErrors = Partial<Record<"username" | "password", string>>;

export function LoginForm() {
  const navigate = useNavigate();
  const { setToken } = useAuth();
  const { refresh } = useCurrentUser();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);

  const canSubmit = useMemo(() => username.trim().length > 0 && password.length > 0, [password.length, username]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    const nextErrors: FieldErrors = {};
    if (!username.trim()) nextErrors.username = "Usuario requerido";
    if (!password) nextErrors.password = "Contraseña requerida";
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    try {
      setSubmitting(true);
      const res = await authApi.login({ username: username.trim(), password });
      setToken(res.access_token);
      await refresh();
      navigate(paths.scenarios, { replace: true });
    } catch (err) {
      const apiError = normalizeAxiosError(err);
      setFormError(apiError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="loginForm">
      <TextField
        label="Usuario"
        autoComplete="username"
        placeholder="nombre de usuario"
        startIcon={<UserIcon />}
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        disabled={submitting}
        {...(fieldErrors.username ? { error: fieldErrors.username } : {})}
      />
      <TextField
        label="Contraseña"
        type="password"
        autoComplete="current-password"
        placeholder="Ingresa tu contraseña"
        startIcon="*"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        disabled={submitting}
        {...(fieldErrors.password ? { error: fieldErrors.password } : {})}
      />

      {formError ? (
        <div role="alert" className="loginErrorBox">
          {formError}
        </div>
      ) : null}

      <Button type="submit" variant="primary" disabled={!canSubmit || submitting} className="loginSubmit">
        {submitting ? "Verificando..." : "Continuar"}
      </Button>
    </form>
  );
}

