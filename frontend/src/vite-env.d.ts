/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_APP_ENV?: "development" | "production" | "staging" | "test" | string;
  readonly VITE_SIMULATION_MODE?: "mock" | "api" | string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

