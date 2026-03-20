# Frontend OSeMOSYS — React + Vite + TypeScript

Interfaz web para el sistema de planificación energética OSeMOSYS. Consume la API FastAPI del backend para gestionar escenarios, ejecutar simulaciones y visualizar resultados.

Guía completa de pruebas E2E: [README_E2E.md](../README_E2E.md).

---

## Stack tecnológico

- **React 19** — UI
- **Vite 7** — Build y dev server
- **TypeScript** — Tipado estático
- **React Router 7** — Enrutamiento con lazy loading
- **Recharts** — Gráficas (despacho, capacidad, emisiones, sectores)
- **Axios** — Cliente HTTP con interceptor JWT

---

## Requisitos

- **Node.js >= 20.19** (recomendado para ESLint v10)
- npm

---

## Instalación y ejecución

```bash
npm install
npm run dev
```

Abre `http://localhost:5173` (o el puerto que indique Vite).

---

## Variables de entorno

Este proyecto usa archivo `.env` (no `.env.example`).

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | URL base de la API | `http://localhost:8010/api/v1` (dev) o `/api/v1` (producción con proxy) |
| `VITE_SIMULATION_MODE` | Modo de simulación | `api` (endpoints reales) |

Archivos típicos:

- `.env` — configuración principal del frontend
- `.env.development` — desarrollo local
- `.env.production` — build para producción

## Archivos que no debes subir

- `.env.local` y variantes locales con credenciales.
- `node_modules/`.
- `dist/` y `build/` generados por compilación.
- artefactos de backend local en `backend/tmp/` (si trabajas con ambos proyectos en el mismo repo).

---

## Scripts disponibles

| Script | Descripción |
|--------|-------------|
| `npm run dev` | Servidor de desarrollo (Vite) |
| `npm run build` | Build de producción (TypeScript + Vite) |
| `npm run preview` | Vista previa del build |
| `npm run typecheck` | Verificación de tipos (tsc) |
| `npm run lint` | ESLint |
| `npm run format` | Prettier (formatear) |
| `npm run format:check` | Prettier (solo verificar) |

---

## Estructura de carpetas

```
src/
├── app/           # Bootstrap, router, providers (Auth, Toast, CurrentUser)
├── routes/       # Rutas, guards (RequireAuth, RequireCatalogManager, etc.)
├── layouts/      # AppLayout (sidebar + header), AuthLayout
├── pages/        # Páginas (lazy loaded)
├── features/     # Módulos por dominio (auth, scenarios, simulation, etc.)
├── shared/       # Componentes, API, errores, storage, hooks
└── types/        # Tipos de dominio (Scenario, SimulationRun, RunResult, etc.)
```

---

## Características principales

- **Lazy loading**: las páginas se cargan bajo demanda (code-splitting); el bundle principal se redujo de ~606KB a ~98KB.
- **Router unificado**: un solo `AppLayout` compartido para todas las rutas protegidas; sidebar con enlace "Inicio".
- **Barra de progreso de subida**: componente `UploadProgress` para importación Excel (Carga oficial, importación en escenarios).
- **Modal con Escape**: el componente `Modal` cierra con la tecla Escape.
- **Tipos de simulación**: `SimulationRun` usa `queued_at` (fecha de encolado) en lugar de `created_at`.

---

## Integración con el backend

**Opción A (recomendada):** reverse-proxy en Nginx con `/api`.

- `VITE_API_BASE_URL=/api/v1`
- En Docker Compose, el frontend (Nginx) proxea `/api/*` hacia el backend.

**Opción B:** URL absoluta del backend (solo desarrollo).

- `VITE_API_BASE_URL=http://localhost:8010/api/v1`
- Configurar CORS en FastAPI.

---

## Levantar stack completo

```bash
# Backend (API + DB + Redis)
cd ../backend
docker compose up --build

# Frontend (dev contra backend Docker)
cd ../frontend
npm install
npm run dev
```

---

## Build para producción (sin Docker)

```bash
npm run build
npm run preview
```

## Docker (imagen de producción)

```bash
docker build -t osemosys-frontend .
docker run --rm -p 8080:80 osemosys-frontend
```

Abre `http://localhost:8080`.
