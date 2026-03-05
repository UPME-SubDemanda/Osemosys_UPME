## Arquitectura (backend)

### Stack

- **API**: FastAPI
- **DB**: Postgres
- **ORM**: SQLAlchemy 2.x (síncrono) + `psycopg`
- **Migraciones**: Alembic
- **Auth**: JWT (HS256)

### Estructura de carpetas

- `app/main.py`: factory y app FastAPI
- `app/core/`: configuración, logging y seguridad
- `app/db/`: engine, sesión y base declarativa
- `app/models/`: modelos ORM
  - `app/models/core/`: schema `core` (usuarios)
  - `app/models/*`: schema `osemosys` (modelo principal)
- `app/schemas/`: schemas Pydantic (request/response)
- `app/repositories/`: acceso a datos (solo consultas/operaciones DB)
- `app/services/`: reglas de negocio (validaciones, paginación, permisos)
- `app/api/v1/`: endpoints versionados (solo llaman services)
  - `app/api/v1/api.py`: registro explícito de routers
- `alembic/`: scripts de migración
- `scripts/seed.py`: datos de prueba idempotentes

### Schemas Postgres

- `osemosys`: tablas del dominio del modelo (scenario, parameter_value, etc.)
- `core`: tablas transversales (por ejemplo `user`)

### Flujo de migraciones

- `alembic/env.py` configura `include_schemas=True` para soportar múltiples schemas.
- Las migraciones crean schemas explícitamente (`CREATE SCHEMA IF NOT EXISTS ...`).

### Autenticación

- Login: `POST /api/v1/auth/login` (form-data `username`, `password`)
- JWT con claim `sub` = `user_id` (**UUID** serializado a string).
- Autorización: header `Authorization: Bearer <token>`

### Respuesta estándar para listados

Los endpoints de listado retornan:

- `data`: lista de items
- `meta`: metadatos de paginación

Convención:
- `offset` es el número de página (1-based)
- `cantidad` es el tamaño de página

