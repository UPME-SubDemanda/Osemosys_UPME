#!/usr/bin/env bash
set -euo pipefail

# Snapshot operativo periódico para el backend separado.
# Registra disco/RAM del host, branch/commit desplegados, stats de contenedores
# y actividad reciente de escenarios/jobs sin tocar el código de la aplicación.

BASE_DIR="${BASE_DIR:-$HOME/osemosys-monitoring}"
LOG_DIR="${LOG_DIR:-$BASE_DIR/logs}"
BACKEND_DIR="${BACKEND_DIR:-$HOME/osemosys-backend/backend}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$LOG_DIR"
cd "$BACKEND_DIR"

stamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
day="$(date -u +%Y%m%d)"
host="$(hostname -s 2>/dev/null || hostname)"

resource_csv="$LOG_DIR/resource_snapshots-$day.csv"
activity_csv="$LOG_DIR/recent_activity-$day.csv"
active_jobs_csv="$LOG_DIR/active_jobs-$day.csv"
container_csv="$LOG_DIR/container_stats-$day.csv"

if [[ ! -f "$resource_csv" ]]; then
  echo "timestamp,host,disk_free_gb,disk_total_gb,disk_used_pct,mem_used_bytes,mem_available_bytes,swap_used_bytes,backend_branch,backend_commit,frontend_branch,frontend_commit" > "$resource_csv"
fi
if [[ ! -f "$activity_csv" ]]; then
  echo "timestamp,running_jobs,queued_jobs,total_jobs_visible,scenarios_created_5m,simulation_jobs_created_5m,parameter_edits_5m" > "$activity_csv"
fi
if [[ ! -f "$active_jobs_csv" ]]; then
  echo "timestamp,job_id,status,username,scenario_id,scenario_name,solver_name,queued_at,started_at" > "$active_jobs_csv"
fi
if [[ ! -f "$container_csv" ]]; then
  echo "timestamp,container_name,cpu_perc,mem_usage,mem_perc" > "$container_csv"
fi

read -r disk_total_gb _disk_used_gb disk_free_gb disk_used_pct _mount_point < <(
  df -BG --output=size,used,avail,pcent,target / | tail -n 1 | awk '{gsub(/G/,"",$1); gsub(/G/,"",$2); gsub(/G/,"",$3); gsub(/%/,"",$4); print $1, $2, $3, $4, $5}'
)
read -r mem_used mem_available < <(free -b | awk '/^Mem:/ {print $3, $7}')
swap_used="$(free -b | awk '/^Swap:/ {print $3}')"

backend_branch="na"
backend_commit="na"
frontend_branch="na"
frontend_commit="na"
if git -C "$HOME/osemosys-backend" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  backend_branch="$(git -C "$HOME/osemosys-backend" rev-parse --abbrev-ref HEAD 2>/dev/null || echo na)"
  backend_commit="$(git -C "$HOME/osemosys-backend" rev-parse --short HEAD 2>/dev/null || echo na)"
fi
if git -C "$HOME/osemosys" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  frontend_branch="$(git -C "$HOME/osemosys" rev-parse --abbrev-ref HEAD 2>/dev/null || echo na)"
  frontend_commit="$(git -C "$HOME/osemosys" rev-parse --short HEAD 2>/dev/null || echo na)"
fi

echo "$stamp,$host,$disk_free_gb,$disk_total_gb,$disk_used_pct,$mem_used,$mem_available,$swap_used,$backend_branch,$backend_commit,$frontend_branch,$frontend_commit" >> "$resource_csv"

docker ps --format '{{.Names}}' | grep '^osemosys-backend-' | while read -r cname; do
  docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}' "$cname" >> "$container_csv.tmp" 2>/dev/null || true
done
if [[ -f "$container_csv.tmp" ]]; then
  while IFS= read -r line; do
    [[ -n "$line" ]] && echo "$stamp,$line" >> "$container_csv"
  done < "$container_csv.tmp"
  rm -f "$container_csv.tmp"
fi

sql_counts="copy (
select
  coalesce(sum(case when status = 'RUNNING' then 1 else 0 end), 0) as running_jobs,
  coalesce(sum(case when status = 'QUEUED' then 1 else 0 end), 0) as queued_jobs,
  count(*) as total_jobs_visible,
  (select count(*) from osemosys.scenario where created_at >= now() - interval '5 minutes') as scenarios_created_5m,
  (select count(*) from osemosys.simulation_job where queued_at >= now() - interval '5 minutes') as simulation_jobs_created_5m,
  (select count(*) from osemosys.parameter_value_audit where created_at >= now() - interval '5 minutes') as parameter_edits_5m
from osemosys.simulation_job
) to stdout with csv"

counts_line="$(docker compose exec -T db psql -U "${POSTGRES_USER:-osemosys}" -d "${POSTGRES_DB:-osemosys}" -Atqc "$sql_counts" 2>/dev/null || true)"
if [[ -n "$counts_line" ]]; then
  echo "$stamp,$counts_line" >> "$activity_csv"
fi

sql_active_jobs="copy (
select
  '${stamp}' as timestamp,
  j.id,
  j.status,
  coalesce(u.username, ''),
  j.scenario_id,
  replace(coalesce(s.name, ''), ',', ' ') as scenario_name,
  j.solver_name,
  to_char(j.queued_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'),
  coalesce(to_char(j.started_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'), '')
from osemosys.simulation_job j
left join core.\"user\" u on u.id = j.user_id
left join osemosys.scenario s on s.id = j.scenario_id
where j.status in ('QUEUED','RUNNING')
order by j.status desc, j.queued_at asc
) to stdout with csv"

docker compose exec -T db psql -U "${POSTGRES_USER:-osemosys}" -d "${POSTGRES_DB:-osemosys}" -Atqc "$sql_active_jobs" 2>/dev/null >> "$active_jobs_csv" || true

find "$LOG_DIR" -type f -name '*.csv' -mtime +"$RETENTION_DAYS" -delete
