/**
 * LoginPage - Página de inicio de sesión
 *
 * Presenta el formulario de login (LoginForm) dentro de una Card.
 * El componente LoginForm maneja la autenticación contra el backend.
 */
import { LoginForm } from "@/features/auth/components/LoginForm";
import { Card } from "@/shared/components/Card";

export function LoginPage() {
  return (
    <Card>
      <div className="loginHeader">
        <div className="loginAccentBar" aria-hidden="true" />
        <p className="loginKicker">Iniciar sesión</p>
        <h1 className="loginTitle">Acceso a la plataforma</h1>
        <p className="loginLead">
          Ingresa para gestionar escenarios, ejecutar simulaciones y consultar resultados consolidados
          del modelo energético.
        </p>
      </div>
      <LoginForm />
    </Card>
  );
}

