# CI/CD de OSeMOSYS

## Qué valida CI

- `docker compose config -q` para validar sintaxis y variables.
- Frontend con `npm ci`, `npm run typecheck` y `npm run build`.
- Backend con `docker compose run --rm api python -m pytest -q`.
- Build de imágenes `api`, `simulation-worker` y `frontend`.

## Cuándo despliega CD

- `pull_request`: solo ejecuta CI.
- `push` a `develop` o `main`: ejecuta CI.
- `push` a `main`: además despliega en el runner `self-hosted`.
- `workflow_dispatch`: sigue pasando por el workflow, pero el deploy solo corre sobre `main`.

## Variables esperadas en GitHub Actions

- `vars.COMPOSE_PROJECT_NAME`
- `vars.FRONTEND_BIND_HOST`
- `vars.FRONTEND_PORT`
- `vars.FRONTEND_API_UPSTREAM` (ej. `api:8000` o `osemosys-backend-api:8000`)
- `vars.BACKEND_BRIDGE_NETWORK` (por defecto `osemosys_api_bridge`)
- `vars.API_BIND_HOST`
- `vars.API_PORT`
- `vars.API_WORKERS`
- `vars.POSTGRES_BIND_HOST`
- `vars.POSTGRES_PORT`
- `vars.REDIS_BIND_HOST`
- `vars.REDIS_PORT`
- `vars.BACKUP_BEFORE_MIGRATIONS`
- `vars.BACKUP_DIR`
- `vars.BACKUP_RETENTION_DAYS`
- `vars.RUN_SEED`
- `vars.SYNC_APP_USERS`
- `vars.SIM_WORKER_REPLICAS`
- `vars.SIM_MAX_CONCURRENCY`
- `vars.SIM_USER_ACTIVE_LIMIT`
- `vars.APP_USERS`
- `vars.APP_ADMIN_USERS`
- `vars.VITE_API_BASE_URL`
- `vars.VITE_APP_ENV`
- `vars.VITE_SIMULATION_MODE`

## Secretos requeridos

- `secrets.APP_PASSWORD`
- `secrets.SECRET_KEY`

## Exposición de servicios

- Por defecto solo el `frontend` debe quedar expuesto.
- Usa `API_BIND_HOST=127.0.0.1`, `POSTGRES_BIND_HOST=127.0.0.1` y `REDIS_BIND_HOST=127.0.0.1`.
- Abre en firewall solo el puerto del frontend del ambiente objetivo.
- El deploy crea la red compartida si no existe.
- Para cutover al backend separado, define `FRONTEND_API_UPSTREAM=osemosys-backend-api:8000`.
- Usa la red Docker compartida `osemosys_api_bridge` para que el frontend alcance el backend nuevo sin exponerlo públicamente.
- El workflow fuerza checkout limpio del `GITHUB_SHA` y rechaza `SECRET_KEY` placeholder.

## Despliegue local/manual

```bash
cp .env.example .env
cp backend/.env.example backend/.env
SECRET_KEY="$(openssl rand -hex 32)" APP_PASSWORD='Cambio123!' ./scripts/deploy-local.sh
```

## Workers del API

- `API_WORKERS=3` deja el API con 3 procesos `uvicorn` por defecto.
- Sube ese valor si necesitas más concurrencia; no acelera mucho una sola importación pesada.
