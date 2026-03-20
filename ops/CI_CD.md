# CI/CD de OSeMOSYS

## Qué valida CI

- `docker compose config -q` para validar sintaxis y variables.
- Frontend con `npm ci`, `npm run typecheck` y `npm run build`.
- Backend con `docker compose run --rm api python -m pytest -q`.
- Build de imágenes `api`, `simulation-worker` y `frontend`.

## Cuándo despliega CD

- `pull_request`: solo ejecuta CI.
- `push` a `main`: ejecuta CI y luego despliega en el runner `self-hosted`.
- `workflow_dispatch`: permite disparar despliegue manual.

## Variables esperadas en GitHub Actions

- `vars.FRONTEND_PORT`
- `vars.FRONTEND_API_UPSTREAM` (ej. `api:8000` o `osemosys-backend-api:8000`)
- `vars.BACKEND_BRIDGE_NETWORK` (por defecto `osemosys_api_bridge`)
- `vars.API_WORKERS`
- `vars.POSTGRES_PORT`
- `vars.BACKUP_BEFORE_MIGRATIONS`
- `vars.BACKUP_DIR`
- `vars.BACKUP_RETENTION_DAYS`
- `vars.RUN_SEED`
- `vars.SIM_WORKER_REPLICAS`
- `vars.SIM_MAX_CONCURRENCY`
- `vars.SIM_USER_ACTIVE_LIMIT`
- `vars.APP_USERS`
- `vars.APP_ADMIN_USERS`

## Secretos requeridos

- `secrets.APP_PASSWORD`

## Exposición de servicios

- Define `POSTGRES_BIND_HOST=0.0.0.0` para acceso desde VPN/LAN.
- Define `POSTGRES_BIND_HOST=127.0.0.1` para dejar Postgres solo local.
- Abre el puerto publicado en firewall si quieres acceso remoto.
- El deploy crea la red compartida si no existe.
- Para cutover al backend separado, define `FRONTEND_API_UPSTREAM=osemosys-backend-api:8000`.
- Usa la red Docker compartida `osemosys_api_bridge` para que el frontend alcance el backend nuevo sin exponerlo públicamente.

## Despliegue local/manual

```bash
cp .env.example .env
cp backend/.env.example backend/.env
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py
```

## Workers del API

- `API_WORKERS=3` deja el API con 3 procesos `uvicorn` por defecto.
- Sube ese valor si necesitas más concurrencia; no acelera mucho una sola importación pesada.
