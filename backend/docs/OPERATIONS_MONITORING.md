# Monitoreo Operativo del Backend

## Objetivo

Registrar cada 5 minutos un snapshot operativo del backend separado sin modificar la aplicación:

- espacio libre en disco
- RAM y swap del host
- branch y commit desplegados
- uso de CPU/RAM por contenedor del stack
- jobs activos de simulación
- escenarios creados recientemente
- jobs de simulación creados recientemente
- cambios recientes sobre `parameter_value_audit`

## Script versionado

- Ruta: `backend/scripts/ops_snapshot.sh`

## Archivos generados

Por defecto se escriben en `~/osemosys-monitoring/logs/`:

- `resource_snapshots-YYYYMMDD.csv`
- `recent_activity-YYYYMMDD.csv`
- `active_jobs-YYYYMMDD.csv`
- `container_stats-YYYYMMDD.csv`

La retención por defecto es de 7 días (`RETENTION_DAYS=7`).

## Instalación por cron

```bash
mkdir -p ~/osemosys-monitoring/logs
chmod +x ~/osemosys-backend/backend/scripts/ops_snapshot.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/procesa01/osemosys-backend/backend/scripts/ops_snapshot.sh >/dev/null 2>&1") | crontab -
```

## Limitaciones actuales

- La creación de escenarios sí queda visible porque `osemosys.scenario` tiene `created_at`.
- Los jobs nuevos sí quedan visibles porque `osemosys.simulation_job` tiene `queued_at`.
- Las ediciones de valores de parámetros sí quedan visibles por `osemosys.parameter_value_audit`.
- Las ediciones de metadata del escenario no tienen una auditoría dedicada ni `updated_at`, así que no se pueden reconstruir bien sin cambios de aplicación.
