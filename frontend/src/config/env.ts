/**
 * Variables de entorno de la aplicación (Vite import.meta.env).
 * apiBaseUrl es obligatoria; appEnv y simulationMode tienen valores por defecto.
 */
function required(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (!value || value.trim().length === 0) {
    throw new Error(`Falta variable de entorno requerida: ${String(name)}`);
  }
  return value;
}

export const env = Object.freeze({
  apiBaseUrl: required("VITE_API_BASE_URL"),
  appEnv: import.meta.env.VITE_APP_ENV ?? "development",
  simulationMode: import.meta.env.VITE_SIMULATION_MODE ?? "api",
});

