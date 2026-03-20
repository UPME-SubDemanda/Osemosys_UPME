import { useAuth } from "@/features/auth/hooks/useAuth";
import { paths } from "@/routes/paths";
import { Button } from "@/shared/components/Button";
import { Link } from "react-router-dom";

export function HomeHeader() {
  const { isAuthenticated } = useAuth();

  return (
    <section style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <div>
        <h1 style={{ margin: 0 }}>Sistema OSeMOSYS</h1>
        <p style={{ margin: "6px 0 0", opacity: 0.8 }}>
          Planeación energética con escenarios, simulación y análisis de resultados.
        </p>
      </div>

      {!isAuthenticated && (
        <Link to={paths.login} style={{ textDecoration: "none" }}>
          <Button variant="primary">Ir a Login</Button>
        </Link>
      )}
    </section>
  );
}

