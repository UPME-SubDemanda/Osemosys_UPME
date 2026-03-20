/**
 * Componente raíz de la aplicación. Renderiza el router (las rutas se cargan dentro de AppProviders).
 */
import { RouterProvider } from "react-router-dom";
import { router } from "@/app/router";

export function App() {
  return <RouterProvider router={router} />;
}

