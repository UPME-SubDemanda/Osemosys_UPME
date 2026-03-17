# CI/CD del backend OSeMOSYS

## Qué valida CI

- `docker compose config -q` dentro de `backend/` para validar sintaxis y variables.
- `docker compose run --rm api python -m pytest -q` para ejecutar las pruebas del backend.
- `docker compose build api simulation-worker` para asegurar que las imágenes del API y del worker compilan.

## Cuándo despliega CD

- `pull_request`: solo ejecuta CI.
- `push` a `develop`: ejecuta CI sin desplegar.
- `push` a `main`: ejecuta CI y luego despliega en el runner `self-hosted`.
- `workflow_dispatch`: permite relanzar el flujo sobre la rama seleccionada; el despliegue sigue restringido a `main`.

## Variables esperadas en GitHub Actions

- `vars.API_BIND_HOST`
- `vars.API_PORT`
- `vars.API_WORKERS`
- `vars.BACKEND_API_ALIAS`
- `vars.BACKEND_BRIDGE_NETWORK`
- `vars.COMPOSE_PROJECT_NAME`
- `vars.POSTGRES_BIND_HOST`
- `vars.POSTGRES_PORT`
- `vars.REDIS_BIND_HOST`
- `vars.REDIS_PORT`
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
- `secrets.SECRET_KEY`

## Exposición de servicios

- El valor recomendado para `API_BIND_HOST` es `127.0.0.1`; así el backend queda cerrado a acceso externo directo.
- Cambia `API_BIND_HOST=0.0.0.0` solo si realmente quieres exponer el API a LAN/VPN.
- Define `POSTGRES_BIND_HOST=127.0.0.1` y `REDIS_BIND_HOST=127.0.0.1` para dejar Postgres y Redis solo locales.
- Usa `COMPOSE_PROJECT_NAME=osemosys-backend` o un valor específico de staging para evitar colisiones con el monorepo actual.
- El deploy crea la red compartida si no existe.
- Si el frontend vive en otro stack Docker, conéctalo a `BACKEND_BRIDGE_NETWORK` y usa `BACKEND_API_ALIAS:8000` como upstream interno.
- Abre únicamente el puerto del API si necesitas acceso remoto; si el frontend usa la red compartida, el backend puede seguir cerrado hacia afuera.
- El despliegue falla si `SECRET_KEY` está ausente o sigue con el valor de ejemplo `change-me`.

## Despliegue local/manual

```bash
cd backend
cp .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py
```

## Smoke tests del despliegue

```bash
cd backend
curl -fsS "http://127.0.0.1:${API_PORT:-18010}/api/v1/health"
curl -fsS "http://127.0.0.1:${API_PORT:-18010}/api/v1/health/ready"
docker compose exec -T simulation-worker sh -lc \
  'celery -A app.simulation.celery_app:celery_app inspect ping -d "simulation-worker@$(hostname)"'
```

## Workers del API

- `API_WORKERS=3` deja el API con 3 procesos `uvicorn` por defecto.
- Sube ese valor si necesitas más concurrencia; no acelera mucho una sola importación pesada.
